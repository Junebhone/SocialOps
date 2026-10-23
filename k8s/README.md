# k8s/ — SocialOps on Amazon EKS (Milestone 5)

Everything the cluster runs, applied with Kustomize. The brief says GKE; on AWS
the stand-in is EKS (`socialops-eks`, us-east-2).

| File | What it is |
|---|---|
| `namespace.yaml`, `serviceaccount.yaml` | namespace `socialops`; IRSA account `socialops-app` (S3, Bedrock; no key files) |
| `configmap.yaml` | non-secret settings (same names as `docker-compose.cloud.yml`) |
| `api-deployment.yaml`, `api-service.yaml` | FastAPI: 2 replicas, startup/liveness/readiness probes |
| `web-deployment.yaml`, `web-service.yaml` | Next.js: 2 replicas, liveness/readiness |
| `worker-deployment.yaml` | arq worker: 1 replica, exec liveness, no Service |
| `redis.yaml` | Redis 7, 1 replica, `emptyDir` (single point of failure by choice) |
| `ingress-api.yaml`, `ingress-web.yaml` | one ALB (group `socialops`), HTTPS, http→https redirect |
| `hpa-api.yaml` | api autoscaler, 2–4 replicas at 30% CPU (demo setting) |
| `pdb.yaml` | PodDisruptionBudgets, `minAvailable: 1`, api and web only |

The Secret `socialops-db` is **not** in git. It is created by command below.
A Kubernetes Secret is base64, not encryption; access to it is what protects it.

## Before applying

Replace the placeholders (Member 3): `socialops.example.com` → our subdomain,
`REPLACE_WITH_ACM_CERT_ARN` → the Issued certificate ARN.

    grep -rn "socialops.example.com\|REPLACE_WITH" k8s/

## Apply

    # 1. Secret, from Secrets Manager, never written to a file
    kubectl -n socialops create secret generic socialops-db \
      --from-literal=DATABASE_URL="$(aws secretsmanager get-secret-value \
        --secret-id socialops/prod/database-url --query SecretString \
        --output text --region us-east-2)"

    # 2. Validate, then apply
    kubectl apply -k k8s/ --dry-run=client
    kubectl apply -k k8s/
    kubectl -n socialops get pods -o wide -w

(The namespace must exist before step 1: `kubectl apply -f k8s/namespace.yaml`.)

## Probe design

| Probe | Endpoint | Checks | If it fails |
|---|---|---|---|
| api startup | `GET /health` | process has booted | keep waiting, up to 150 s |
| api liveness | `GET /health` | process answers. **No database call** | container restarts |
| api readiness | `GET /health/ready` | Postgres **and** Redis reachable (503 if not) | removed from Service and ALB, **no restart** |
| web liveness / readiness | `GET /inbox` | page renders | restart after 30 s / out of rotation after 10 s |
| worker liveness | `arq --check` | arq heartbeat in Redis is fresh (< 31 s old) | container restarts |
| ALB health check | `/health/ready` (api), `/inbox` (web) | second layer, from outside the cluster | target marked unhealthy |

**Liveness never checks the database.** If it did, an RDS blip would fail
liveness on every api pod at once and Kubernetes would restart all of them,
turning a few seconds of database trouble into a full outage. Readiness takes
the pod out of traffic instead, and puts it back by itself when the database
returns. Honest limit: the worker's heartbeat lives in Redis, so a long Redis
outage does restart the worker.

## Evidence (Day 2)

    kubectl -n socialops describe pod -l app=api | grep -A3 -E "Liveness|Readiness|Startup"
    POD=$(kubectl -n socialops get pod -l app=api -o name | head -1)
    kubectl -n socialops exec $POD -- python -c "import urllib.request as u;print(u.urlopen('http://127.0.0.1:8000/health').read().decode())"
    kubectl -n socialops exec $POD -- python -c "import urllib.request as u;print(u.urlopen('http://127.0.0.1:8000/health/ready').read().decode())"

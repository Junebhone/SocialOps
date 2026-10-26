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

## Cluster (Module 01, once)

    aws ec2 create-tags --region us-east-2 \
      --resources subnet-05177c280220c291b subnet-0105402ce73e5e616 \
      --tags Key=kubernetes.io/role/elb,Value=1 Key=kubernetes.io/cluster/socialops-eks,Value=shared
    aws iam create-policy --policy-name socialops-pod-runtime \
      --policy-document file://k8s/iam/pod-runtime.json
    eksctl create cluster -f k8s/cluster/eksctl.yaml        # 15-20 min; also creates
                                                            # socialops-app-irsa, metrics-server
    aws eks update-kubeconfig --name socialops-eks --region us-east-2
    helm repo add eks https://aws.github.io/eks-charts && helm repo update
    helm install aws-load-balancer-controller eks/aws-load-balancer-controller -n kube-system \
      --set clusterName=socialops-eks --set serviceAccount.create=false \
      --set serviceAccount.name=aws-load-balancer-controller \
      --set region=us-east-2 --set vpcId=vpc-0b1aaa0783cc57a44
    # RDS accepts 5432 from the cluster security group
    CSG=$(aws eks describe-cluster --name socialops-eks --region us-east-2 \
      --query cluster.resourcesVpcConfig.clusterSecurityGroupId --output text)
    aws ec2 authorize-security-group-ingress --region us-east-2 \
      --group-id sg-0bd40e4797af7fe3a --protocol tcp --port 5432 --source-group $CSG

Teammates listed under `accessConfig` in `eksctl.yaml` get cluster admin; each runs
the `update-kubeconfig` line once. After the ALB exists, `app` and `api` are
Route 53 alias A records to it in the `socialops.website` zone.

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

## After a drain test

Uncordoning does not move pods back, so after draining both nodes every replica sits on one node.
Spread them again before the next take:

    kubectl -n socialops rollout restart deploy/api deploy/web

## Teardown (right after recording)

    kubectl delete ingress --all -n socialops    # removes the ALB; wait until it is gone
    aws ec2 revoke-security-group-ingress --region us-east-2 \
      --group-id sg-0bd40e4797af7fe3a --protocol tcp --port 5432 --source-group $CSG
    eksctl delete cluster -f k8s/cluster/eksctl.yaml
    aws rds stop-db-instance --db-instance-identifier socialops-db --region us-east-2

Delete the Ingresses first, or the ALB outlives the cluster and keeps billing.
Delete the `app`/`api` alias records too. Then check EC2 for leftover load
balancers, volumes and Elastic IPs.

# Written analysis: the 5xx a missing PodDisruptionBudget causes

*Draft for Module 06 (Member 5: rewrite in your own words, then export to PDF). Numbers are from
`docs/milestone5/evidence/`, measured 2026-10-25.*

**What a missing PodDisruptionBudget does.** A PodDisruptionBudget (PDB) tells Kubernetes how many
replicas must stay up during a voluntary disruption: a node drain for an EKS upgrade, a node-group
rolling update, a scale-down. Without one, Kubernetes evicts every pod on the node at once. If both
api replicas are on that node, the Service has no ready endpoints until the replacements pass
readiness. The ALB also keeps a terminating pod as a target until deregistration finishes, so some
requests reach a pod that is already gone. Users see a few seconds of intermittent 502 and 503
responses, not a clean outage, and `/health` looks fine again by the time anyone checks, which makes
it hard to diagnose.

**What our configuration did.** api and web run two replicas with a hard topology spread (one per
node, `DoNotSchedule`), `maxUnavailable: 0`, a 10 second preStop sleep, and a PDB with
`minAvailable: 1`. We drained node A and then node B with a curl loop running against
`https://api.socialops.website/health`. Kubernetes refused the last eviction on node B
("Cannot evict pod as it would violate the pod's disruption budget"), so one api pod kept serving
and the app never went to zero. It was not perfectly clean: 337 of 360 requests returned 200, with
22 timeouts and one 503, nearly all while node A drained. A second run with the ALB IP pinned
failed the same way, so the cause is not DNS. It is the ALB still sending to the evicted pod during
deregistration. The PDB turns a full outage into a short blip; it does not remove the blip.

**Limits.** A PDB only guards evictions. `kubectl delete pod` and a node crash are not covered, which
is why we also run two or more replicas on different nodes. (Deleting an api pod directly under the
same curl loop gave 120 of 120 successes, because the other replica kept serving.) The worker and
redis are single replicas on purpose: a PDB on one pod would block every drain forever, and redis
loses queued jobs when it restarts. Our own test showed the cost of that: draining the second node
evicted redis, and the api's readiness check, which needs redis, went red until redis came back.

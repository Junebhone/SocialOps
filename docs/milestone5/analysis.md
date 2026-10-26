# Written Analysis: Missing PodDisruptionBudgets and Intermittent 5xx Errors

*Module 06. Submitted as `M5_Written_Analysis_PDB_v2.pdf`; this is the same text. Numbers are from
`docs/milestone5/evidence/`, measured 2026-10-25.*

## 1. The intermittent 5xx failure a missing PodDisruptionBudget causes

A node drain, node-group update or scale-down is a **voluntary disruption**. Without a
PodDisruptionBudget, Kubernetes may evict every pod on the node at once. If both api replicas are
there, the Service has no ready endpoints until replacements pass readiness, while the load balancer
still sends requests to pods that are shutting down. The result is **intermittent**: some
requests get 502 or 503, others succeed, and after a few seconds everything is healthy again, so the
cause is hard to find afterwards.

## 2. Our team never experienced it: why our configuration prevented it

api and web each have a PDB with minAvailable: 1, run one replica per node under a hard topology
spread (our first, soft rule once put both api replicas on one node), use maxUnavailable: 0, and
pause 10 seconds before shutdown. When we drained both nodes, Kubernetes refused the last eviction,
so one api pod always kept serving. It was not error-free: **337 of 360**
requests in a curl loop succeeded, and the rest failed briefly while the load balancer deregistered
the evicted pod. The PDB turned an outage into a blip.

## 3. Limits

A PDB only guards evictions, not **kubectl delete pod** or a node crash; two replicas on
different nodes cover those (a direct delete gave 120 of 120 successes). The worker and Redis are
single replicas by choice, since a PDB on one pod blocks every drain.

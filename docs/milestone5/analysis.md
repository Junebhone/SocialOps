# Written Analysis: Missing PodDisruptionBudgets and Intermittent 5xx Errors

*Module 06. Submitted as `M5_Written_Analysis_PDB_v2.pdf`; this is the same text. Numbers are from
`docs/milestone5/evidence/`, measured 2026-10-25.*

## The failure a missing PDB causes

A node drain, node-group update or scale-down is a **voluntary disruption**. Without a
PodDisruptionBudget, Kubernetes may evict every pod on the node at once. If both api replicas are
there, the Service has no ready endpoints until replacements pass readiness, and the load balancer
still sends some requests to pods that are shutting down. Users see **scattered 502 and 503
responses for a few seconds**, and the pods look healthy again by the time anyone checks.

## Why our configuration prevented it

We never had that outage. api and web each have a PDB with minAvailable: 1, run one replica per
node under a hard topology spread (our first, soft rule once put both api replicas on one node), use
maxUnavailable: 0, and pause 10 seconds before shutdown. When we drained both nodes, Kubernetes
refused the last eviction, so one api pod kept serving. It was not error-free: **337 of 360**
requests in a curl loop succeeded, and the rest failed briefly while the load balancer deregistered
the evicted pod. The PDB turned an outage into a blip.

## Limits

A PDB only guards evictions, not **kubectl delete pod** or a node crash; two replicas on
different nodes cover those (a direct delete gave 120 of 120 successes). The worker and Redis are
single replicas by choice, since a PDB on one pod blocks every drain.

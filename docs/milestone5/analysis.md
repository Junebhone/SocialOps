# Written Analysis: Missing PodDisruptionBudgets and Intermittent 5xx Errors

SocialOps · Milestone 5 · EDS 6348 Group 5 · Amazon EKS socialops-eks, us-east-2

*Module 06. Submitted as `M5_Written_Analysis_PDB_v2.pdf`; this is the same text. Numbers are from
`docs/milestone5/evidence/`, measured 2026-10-25.*

## The intermittent 5xx failure a missing PDB causes

A node drain, node-group update or scale-down is a **voluntary disruption**. Without a
PodDisruptionBudget, Kubernetes may evict every pod on a node at once. If both api replicas are
there, the Service has no ready endpoints until replacements pass readiness, while the load balancer
still routes requests to pods that are shutting down. Users see **scattered 502 and 503 responses
for a few seconds**, then the pods look healthy again, which is why it is intermittent and hard
to diagnose.

## What we saw, and why our configuration prevented the outage

api and web run two replicas, one per node (a hard topology spread), with maxUnavailable: 0, a
10-second preStop pause, a readiness probe on /health/ready, and a PDB with minAvailable: 1. On 25
October we drained both nodes while a curl loop called the api every half second. The PDB held:
Kubernetes refused to evict the last api and web pods ("Cannot evict pod as it would violate
the pod's disruption budget"), so the app never went to zero. We did see the intermittent
failure in a small form: **337 of 360** requests returned 200, with 22 timeouts and one 503 while
the load balancer deregistered the evicted pod. Without the PDB the last api pod would have been
evicted too. The PDB turns an outage into a short blip; it does not remove the blip.

## Limits

A PDB only guards evictions, not **kubectl delete pod** or a node crash; two replicas on
different nodes cover those (a direct delete gave 120 of 120 successes). The worker and Redis are
single replicas by choice, since a PDB on one pod blocks every drain.

# Milestone 5 test evidence (2026-10-25, cluster socialops-eks)

Raw outputs are in this folder. Load came from pods inside the cluster calling the public
`https://api.socialops.website` through the ALB (host `curl` is not used). These are dry runs for
the video; the video still records each test live.

| Test | Result | Files |
|---|---|---|
| Delete one api pod under a curl loop (0.5 s) | replacement Ready in ~15 s; **120 / 120 requests 200** | (captured in session; rerun on camera) |
| HPA under load (3 pods x 8 parallel curls on `/health/ready`) | CPU 1% → 231% of request; **2 → 4 replicas**, `SuccessfulRescale`; back to 2 after load stopped | (captured in session; rerun on camera) |
| Drain node A, then node B, PDB in place | B's drain refused: `Cannot evict pod as it would violate the pod's disruption budget` (9 refusals each for api, web, coredns, metrics-server); one api pod kept serving | `drain-0..4-*.txt` |
| curl loop during both drains | **337 / 360 200**, 22 timeouts (`000`) while A drained, 1 × 503 | `drain-curl-codes.txt` |
| Drain node A again, curl by pinned ALB IP vs. DNS | both columns: 196-197 / 200 200, 2-3 × `000`, 1 × 502 | `drain-curl-pinned-vs-dns.txt` |

What the drain numbers mean: the PDB stops a drain from taking api to zero, but it does not make a
drain free. The pinned-IP column fails the same way as the DNS column, so it is not cluster DNS. The
few errors are the ALB still sending to the evicted pod while its target deregisters. Draining the
second node also evicts redis (single replica, no PDB by design), which turns the surviving api pod's
readiness red until redis is back: a dependency the PDB cannot protect.

Not done: the optional "remove the PDB and drain" reproduction from the plan.

# Before recording: final checklist

## Already done and verified
- [x] Live app, API health, HTTPS certificate
- [x] JSON logs, metric filter, controlled 5xx evidence (request id, log line, metric = 1)
- [x] Dashboard, alarm, SNS, received ALARM and OK emails
- [x] Pipeline: good run, failed run with automatic rollback, revert run
- [x] `terraform plan` clean after three deploys (CloudShell output saved, plus Dan's screenshot)
- [x] Security and cost controls verified
- [x] Written analysis (one page), full slide deck, artifact pack, recording script

## To do before you press record
- [ ] **Screenshots still missing** (optional, send them and I will save them):
  1. ~~Rollback Summary page~~ not needed: the Roll back step screenshot (`pipeline-rollback-step.png`) is saved and is better evidence.
  2. **ECS services, current**: ECS → Clusters → socialops-dev → Services. Must show `api:5`, `worker:5`, `web:4`, 1/1 running. (Dan's was from Nov 6 and shows `:1`; do not use it.)
  3. Optional: SNS subscription **Confirmed**; Budget `SocialOps-Budget`.
- [ ] **Make the 2-slide deck** from `README_DESIGN_2_SLIDES.md` and open it for a check.
- [ ] **Merge the docs PR** (#23) once its checks are green.
- [ ] **Warm up CloudShell** (see the cue sheet) so the live plan is quick.
- [ ] **Agree who presents what** (see the cue sheet). If Dan is not presenting, Member 3 does the live plan.
- [ ] **Dry-run the two pushes** by reading the scripts (`scripts/demo/push-good.sh`, `push-bad.sh`, `push-fix.sh`). Do not run them until recording.
- [ ] Route off (404), alarm OK, notifications closed, personal tabs hidden, cameras working.

## After the recording
- [ ] `push-fix.sh`, wait for green, plan clean again
- [ ] Upload to OneDrive, share with the three instructors, test signed-out, submit the link in Canvas
- [ ] Confirm the app stays up during the grading period (and that the budget alert still exists)

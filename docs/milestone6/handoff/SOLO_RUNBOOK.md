# Solo runbook: one presenter, one take, every rubric line

You are the only presenter. Your face must be visible the whole time (use Zoom or Teams: share your screen **with your camera on and visible**, record to the cloud or locally). Target: about 15 minutes after you cut the waits.

The trick: the pipeline is slow (good deploy about 7.5 min, bad deploy about 12 min). Pipelines cannot run at the same time, but **you can do other segments while one runs**. So the order below is not the order of the rubric; it is the order that wastes no time. Every rubric item still appears.

---

## T-minus 30 minutes: preparation (off camera)

1. **Merge PR #23** first. The demo scripts live in it, and they must be on `main` before you run them. (Ask Claude: "merge #23".)
2. **Fresh clone for the scripts** (keeps your working copy out of it):
   `git clone https://github.com/Junebhone/SocialOps.git ~/demo-repo && cd ~/demo-repo && git log --oneline -1`
   Check `ls scripts/demo` shows `push-good.sh push-bad.sh push-fix.sh open-tabs.sh`.
3. **Open the tabs:** `bash ~/demo-repo/scripts/demo/open-tabs.sh` (opens 10). Sign in to AWS and GitHub. Close everything else. Hide bookmarks, other tabs, notification banners. Turn on Do Not Disturb.
4. **Error route must be OFF:** `curl -s -o /dev/null -w "%{http_code}\n" https://api.socialops.website/debug/error` → **404**.
5. **Alarm shows OK** (tab 6).
6. **Warm up CloudShell** (tab 10) so the live plan is fast. Paste these two lines (put your real values where the angle brackets are; **never show these lines on camera**), wait until the last line says "No changes":
   ```
   cd ~/so && git pull -q && cd infra/stack && export PATH=$HOME/bin:$PATH TF_PLUGIN_CACHE_DIR=/tmp/tfcache TMPDIR=/tmp TF_VAR_alert_email="<team alert address>"
   terraform init -input=false -backend-config="bucket=socialops-tfstate-<account id>" > /dev/null && terraform workspace select dev && terraform plan -var-file=env/dev.tfvars | tail -3
   ```
   Then type `clear` so the screen is clean.
7. **Open the slides** (the 2-slide deck) in a separate window. Have the alert email open in your mail client, **showing only the message body** (not the inbox list with your address at the top).
8. **Screen layout:** browser full screen on tab 1. Terminal (for the push scripts) in a second window, large font (18 pt+). CloudShell in tab 10.
9. Do a 30-second test recording to check that the camera and audio are on and your face is visible.

---

## The recording, in the order you do it

### 0:00 · Intro and live app (2 min) · rubric: **live HTTPS URL (4)**, **slides (6)**

Show: the 2-slide deck, slide 1. Then tab 1 (the app), then tab 2 (API health).
Say:
- "This is SocialOps, a multi-agent social media command center. It runs live on AWS at this HTTPS address, with the padlock."
- "The API health endpoint says status ok, database true, redis true."
- Slide 1: "Traffic goes through the load balancer to ECS Fargate. Logs go to CloudWatch, a metric filter counts HTTP 5xx, an alarm fires, SNS emails the team. Deployments run from GitHub Actions: build, deploy, health check, automatic rollback."

### 2:00 · Start the good deploy (1 min) · rubric: **pipeline on push (9)**

In the terminal: `bash ~/demo-repo/scripts/demo/push-good.sh` → type `YES`.
Show: tab 7 (GitHub Actions). Click the new run at the top.
Say:
- "I just pushed one commit to main. Every push to main starts this pipeline: lint and tests, build the images tagged with the commit SHA, then deploy."
- "The deploy job uses an OIDC role, so there are no stored AWS keys."
**Leave it running.** You return in about 7 minutes. Do the next segments meanwhile.

### 3:00 · Controlled 5xx, JSON log, metric (3 min) · rubric: **JSON logs and 5xx metric (7)**

In CloudShell (tab 10):
1. `aws ssm put-parameter --name /socialops-dev/enable-error-route --value true --overwrite`
   Say: "The error route is off by default. One setting switches it on, with no redeploy."
2. `curl -i -H "X-Request-ID: demo-5xx-001" https://api.socialops.website/debug/error`
   Say: "A controlled HTTP 500, with a request id I chose."
3. Immediately turn it off: `aws ssm put-parameter --name /socialops-dev/enable-error-route --value false --overwrite`
   Say: "Switched off again."
4. Tab 3 (Logs Insights). Log group `/ecs/socialops-dev/api`. Run:
   `fields @timestamp, @message | filter request_id = "demo-5xx-001"`
   Say: "One matching line, and it is JSON: status_code 500, the path, the request id, the duration."
5. Tab 4 (Metrics → SocialOps/dev → Api5xxCount, Sum, 1 minute).
   Say: "The metric filter counts every line with status code 500 or higher. It increased by one." (It may take a minute to appear; if not yet, say so and come back.)
6. Show the filter definition: the metric filter screen (`{ $.status_code >= 500 }`, metric `Api5xxCount`, value 1). Backup: `docs/milestone6/evidence/metric-filter.png`.

### 6:00 · Dashboard, alarm policy, received alert (3 min) · rubric: **dashboard and alert received (7)**

Show: tab 5 (dashboard). Say: "Top left is the 5xx count with the alarm threshold at one. Next to it, load balancer requests and errors. Below: CPU and memory for the api, web and worker services, then response time, database CPU, and the alarm state."
Show: tab 6 (alarm), Details tab. Say: "The alarm fires when the sum of 5xx errors is at least one in 60 seconds. Missing data counts as healthy." Then the Actions tab: "ALARM and OK both send a message to our SNS topic."
Show: the alert email (message body only). Say: "This alert email was actually received. This is the alarm. And this is the return to OK." If the alarm email for your test has not arrived yet, show the earlier ones, then say the new one is on its way.
(The first ALARM email for your demo request arrives about a minute after the request.)

### 9:00 · Back to the good deploy (1 min) · rubric: **build, deploy and health check (9)**

Show: the run in tab 7. It should be green.
Open **Deploy (dev)**. Expand **Health check and revision check**. Say: "The health check passed on the first try: the API says ok, the web returns 200, and every running task is on the new revision."
Say: "It recorded the running revisions, ran the migration, registered new task definitions, updated the services and waited for them to be stable, then checked health."
(If it is not finished, wait on screen; cut the waiting in editing. Backup: run 42529005106.)

### 10:00 · Live Terraform plan (2 min) · rubric: **Terraform and live plan with no changes (9)**

CloudShell (tab 10). Only after the deploy is **done**. Run exactly:
```
cd ~/so/infra/stack
terraform workspace show
terraform plan -var-file=env/dev.tfvars
```
Say:
- "This is the dev workspace. Terraform refreshes the real infrastructure first; refresh is on by default."
- When it ends: "No changes. Your infrastructure matches the configuration. And that is after a pipeline deploy, so deploys do not cause drift."
- "What Terraform manages: the network, load balancer with HTTPS, ECS services, database, Redis, S3, SQS, IAM, logging, the metric, the alarm, the dashboard. What it does not: the state bucket and lock table in a separate bootstrap stack, the Route 53 zone, the budget, Bedrock access, the SNS confirmation click, and old Milestone 5 resources. The services ignore task definition changes so deployments are not drift."

### 12:00 · Failed deploy and automatic rollback (2 min on screen, 12 min real) · rubric: **automatic rollback verified (9)**

Terminal: `bash ~/demo-repo/scripts/demo/push-bad.sh` → type `YES`. Show tab 7, click the new run.
Say:
- "This commit is a controlled failure. On ECS only, the readiness endpoint now returns 503. The site itself stays up."
- "The ECS circuit breaker does not catch this, because the containers start and pass their own health check. Our pipeline does."
**Cut the video here** (the run takes about 12 minutes). While it runs you can set the video aside, or just stop and resume recording.
Return when the run is red:
- Open **Deploy (dev)** → **Health check and revision check**: "The health check fails on all ten tries."
- **Roll back** step: "The pipeline restores the previous revisions, waits for stability, and checks again. The old version is running: api revision 3, worker 3, web 2, status ok."
- "The run is red on purpose."
- Terminal: `curl -s https://api.socialops.website/health/ready` → `{"status":"ok","database":true,"redis":true}`. Say: "The previous working version is serving traffic."
(Backup: run 42535888765.)

### 14:30 · Close (30 sec) · rubric: **controls kept, slides (6)**

Show slide 2 (team contributions). Say: "Everything is in Terraform, the pipeline deploys and rolls back automatically, and the earlier controls are still in place: private database, role-based storage access, secrets in Secrets Manager, and budget alerts. Here is who built what."

**Stop recording.**

---

## Right after recording (off camera)

1. `bash ~/demo-repo/scripts/demo/push-fix.sh` → `YES`. Wait for the run to go green.
2. In CloudShell run the plan again → confirm "No changes".
3. Confirm: route off (`/debug/error` → 404), alarm OK, app healthy.
4. Upload the **full video** to OneDrive. Share view access with the three instructors named in the brief. Test the link in a signed-out (private) browser window. Submit the link in Canvas (do not upload the video to Canvas).

---

## Rubric tick sheet (50 points)

| Rubric line | Pts | Where it is satisfied | Done? |
|---|---|---|---|
| JSON logs, log-based metric counts 5xx, controlled error demonstrated | 7 | Segment 3:00: curl 500, JSON line by request id, metric +1, filter definition | Evidence ready; do live |
| Dashboard shows errors and resource usage; alert actually received | 7 | Segment 6:00: dashboard, alarm policy, received email | Evidence ready; do live |
| Terraform covers infrastructure, exceptions explained, live plan with refresh shows no changes | 9 | Segment 10:00: live plan, "No changes", exceptions said aloud; also the analysis | Evidence ready; do live |
| Pipeline builds, deploys, health-checks on every push; automatic rollback demonstrated and verified | 9 | Segments 2:00 + 9:00 (good deploy), 12:00 (bad deploy, rollback, old version serves) | Proven (3 runs); do live |
| Written analysis (1 page) | 8 | `docs/milestone6/Milestone6_Analysis.pdf` | Done |
| Demo and slides, about 15 minutes, clear | 6 | Whole video + the 2-slide deck (slide 1 at start, slide 2 at end) | **You: make the deck, rehearse once** |
| App works at live HTTPS URL at demo time and stays up | 4 | Segment 0:00; keep it running through grading | Live now |

Also required by the brief (not points, but must not be missed):
- [ ] Camera on, your face visible during the whole recording.
- [ ] No secret values on screen: no `.env`, no Secrets Manager values, no AWS keys, no alert email address.
- [ ] Controlled failures only; no data deleted.
- [ ] Repo link with Terraform files, workflow file, and the demonstrated commit SHA in the submission (see the artifact pack).
- [ ] Screenshots of the dashboard, alert policy and a received alert (already in `docs/milestone6/evidence/`).
- [ ] The video goes to OneDrive, shared with the three instructors; link submitted in Canvas.
- [ ] Add the live-demo commit SHAs (from the two runs you start) to the submission note.

## If something goes wrong
- **Metric or alarm email is slow:** say it takes about a minute, show the earlier emails and the screenshots, move on, and come back.
- **Live plan is slow or errors:** cut the wait. If it errors, show `docs/milestone6/evidence/terraform-plan-after-deploy.txt` and `terraform-plan.png` and say so.
- **A pipeline run behaves strangely:** use the recorded runs as backup: good 42529005106, failed and rolled back 42535888765, revert 42537260649.
- **Route still returns 404 after switching on:** wait 10 seconds and try again.
- **You made a mistake:** keep going and cut it in editing. It is fine.

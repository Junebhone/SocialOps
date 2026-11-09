# Demo cue sheet: read this while you record

Target length: about 15 minutes. **Cameras on for every presenter** during their part. No secrets, no `.env`, no email
address on screen. Anything in `quotes` is what to say. Anything after **OPEN** or **RUN** is what to click or type.
Short lines on purpose. Say them in your own voice.

## Before you press record (off camera, 10 minutes)

1. Run `bash scripts/demo/open-tabs.sh`. It opens all the tabs. Sign in to AWS and GitHub.
2. Error route is OFF. Run: `curl -s -o /dev/null -w "%{http_code}\n" https://api.socialops.website/debug/error` → must print **404**.
3. Tab 6 (alarm) shows **OK**. Nobody sends test requests during the recording.
4. **Warm up CloudShell** (tab 10) so the live plan is fast. Paste these two lines and wait for them to finish:
   ```
   cd ~/so && git pull -q && cd infra/stack && export PATH=$HOME/bin:$PATH TF_PLUGIN_CACHE_DIR=/tmp/tfcache TMPDIR=/tmp TF_VAR_alert_email="<the team alert address>"
   terraform init -input=false -backend-config="bucket=socialops-tfstate-<account id>" > /dev/null && terraform workspace select dev && terraform plan -var-file=env/dev.tfvars | tail -3
   ```
   It should end with "No changes". (Replace the two placeholders yourself. Never show that line on camera. After this the variable stays set in the session.)
5. In a terminal, have the repo cloned and clean. The three scripts are in `scripts/demo/`.
6. Close notifications. Hide bookmarks and personal tabs. Share one window at a time.

---

## 0:00 · Presenter: Member 5 · App and architecture (about 2 min)

**OPEN** tab 1 (the app), then tab 2 (API health), then the 2-slide deck.

Say:
- "This is SocialOps, a multi-agent social media command center. It runs live on AWS at this HTTPS address."
- "Here is the app. The padlock shows HTTPS."
- "And the API health endpoint says status ok, database true, redis true."
- "For this milestone we made it observable and automated its deployment."
- Show slide 1: "Traffic goes through the load balancer to ECS Fargate. Logs flow to CloudWatch, a metric filter counts HTTP 5xx, an alarm fires, and SNS emails the team."
- "Deployments run from GitHub Actions: build, deploy, health check, and automatic rollback."

## 2:00 · Presenter: Member 2 (Zainab) · Controlled 5xx, JSON log, metric (about 3 min)

**Before:** turn the route on, then **RUN** (CloudShell):
`aws ssm put-parameter --name /socialops-dev/enable-error-route --value true --overwrite`

Say, then do:
- "The error route is off by default. I switch it on with one setting, no redeploy."
- **RUN** `curl -i -H "X-Request-ID: demo-5xx-001" https://api.socialops.website/debug/error`
- "That is a controlled HTTP 500. Here is the request id."
- **OPEN** tab 3 (Logs Insights). Log group `/ecs/socialops-dev/api`. Query:
  `fields @timestamp, @message | filter request_id = "demo-5xx-001"`
- "One matching line, and it is JSON: status_code 500, the path, the request id, and the duration."
- **OPEN** tab 4 (Metrics → SocialOps/dev → Api5xxCount, Sum, 1 minute).
- "The log-based metric counts every line with status code 500 or higher. It went up by one."
- Show the metric filter: `{ $.status_code >= 500 }`, value 1 (screenshot `metric-filter.png` is a backup).
- **RUN** `aws ssm put-parameter --name /socialops-dev/enable-error-route --value false --overwrite`
- "Switched off again. The route now returns 404."

## 5:00 · Presenter: Member 3 · Dashboard, alarm, received email (about 3 min)

**OPEN** tab 5 (dashboard).

Say:
- "This is the dashboard. Top left is the HTTP 5xx count, with the alarm threshold line at one."
- "Next to it, load balancer requests and 5xx errors."
- "Below, CPU and memory for the api, web and worker services."
- "Then API response time, database CPU, and the alarm state, which is OK."
- **OPEN** tab 6 (alarm), Details tab:
- "The alarm fires when the sum of 5xx errors is at least one in 60 seconds. Missing data counts as healthy."
- Actions tab: "Both ALARM and OK send a message to our SNS topic."
- **OPEN** the inbox with the real alert email (or `alert-email-alarm.png`).
- "This alert email was actually received. This one is the alarm. This one is the return to OK."
- (The alarm email arrives about a minute after the request. Cut or speed up the wait in editing.)

## 8:00 · Presenter: Member 1 (Dan), or Member 3 if Dan is not there · Live Terraform plan (about 2 min)

**OPEN** tab 10 (CloudShell). The variable is already set from the warm-up.

**RUN**
```
cd ~/so/infra/stack
terraform workspace show
terraform plan -var-file=env/dev.tfvars
```
Say:
- "This is the dev workspace. This plan refreshes the real infrastructure first. Refresh is on by default."
- Wait for the result. "No changes. Your infrastructure matches the configuration."
- "That is after three pipeline deployments, so deploys do not create drift."
- "Things we do not manage in Terraform: the state bucket and lock table in a bootstrap stack, the budget, Bedrock model access, the SNS confirmation click, and old Milestone 5 resources."

## 10:00 · Presenter: Member 4 · Push, build, deploy, health check (about 3 min, then cut)

**RUN** (terminal, in the repo): `bash scripts/demo/push-good.sh` → type `YES`.
**OPEN** tab 7 (GitHub Actions) and click the new run.

Say:
- "I just pushed one commit to main. Every push to main starts this pipeline."
- "First lint and tests, then the three images are built and tagged with the commit SHA."
- "Then the deploy job. It uses an OIDC role, so there are no stored AWS keys."
- Open the Deploy job: "It records the running revisions, runs the database migration, registers new task definitions, updates the services, and waits for them to be stable."
- "Then the health check: the API must say ok, the web must return 200, and every running task must be on the new revision."
- **Cut the video here.** The full run takes about 7 minutes. Come back when it is green.
- Green: "Healthy on the new revisions. The deployment succeeded." (Backup: tab 8, run 42529005106.)

## 13:00 · Presenter: Member 4 · Failed deploy, automatic rollback, verify (about 2 min plus cuts)

**RUN** `bash scripts/demo/push-bad.sh` → type `YES`.
**OPEN** tab 7, click the new run.

Say:
- "This commit is a controlled failure. On ECS only, the readiness endpoint now returns 503. The site itself stays up."
- "The ECS circuit breaker does not catch this, because the containers start and pass their own health check."
- **Cut the video** while it deploys (about 8 to 10 minutes).
- Open the Deploy job, step "Health check and revision check": "The health check fails on all ten tries."
- Step "Roll back": "The pipeline restores the previous revisions, waits for stability, and checks again."
- "It shows the old version running: api revision 3, worker 3, web 2. Status ok."
- "The run is red on purpose, and the summary says ROLLED BACK." (Backup: tab 9, run 42535888765.)
- **RUN** `curl -s https://api.socialops.website/health/ready` → `{"status":"ok","database":true,"redis":true}`
- "The previous working version is serving traffic."

## 15:00 · Close (Member 5) · 30 seconds

- "Everything is in Terraform, the pipeline deploys and rolls back automatically, and the controls from earlier milestones are still in place: private database, role-based storage access, secrets in Secrets Manager, and budget alerts."
- Show slide 2: "Here is who built what."

## After you stop recording (off camera)

1. **RUN** `bash scripts/demo/push-fix.sh` → type `YES`. Wait for the run to go green.
2. In CloudShell run `terraform plan -var-file=env/dev.tfvars` again → confirm "No changes".
3. Confirm the route is off (`/debug/error` returns 404) and the alarm is OK.
4. Upload the full video to OneDrive, share view access with the three instructors, test the link signed-out, submit it in Canvas.

## If something goes wrong on camera
- **Live plan is slow:** cut the wait in editing. If it errors, use `evidence/terraform-plan-after-deploy.txt` and `terraform-plan.png`, and say so.
- **Pipeline takes long or fails oddly:** use the recorded runs as backup: good run 42529005106, failed and rolled back run 42535888765, revert run 42537260649.
- **Route still returns 404 after switching on:** wait 10 seconds and try again. The setting is read on every request.
- **Never** show a Secrets Manager value, the `.env` file, the alert email address, or an AWS access key.

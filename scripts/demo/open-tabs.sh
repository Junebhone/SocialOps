#!/usr/bin/env bash
# Opens every browser tab for the Milestone 6 demo, in the order they are used,
# and prints what to do. macOS only (uses `open`). Read-only: changes nothing.
# Usage: bash scripts/demo/open-tabs.sh
R=https://github.com/Junebhone/SocialOps
CW="https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1"
tabs=(
  "https://app.socialops.website"                                   # 1  live app
  "https://api.socialops.website/health/ready"                      # 2  API health
  "$CW#logsV2:logs-insights"                                        # 3  find the JSON log line
  "$CW#logsV2:log-groups/log-group/\$252Fecs\$252Fsocialops-dev\$252Fapi"   # 4  metric filter (Metric filters tab)
  "$CW#dashboards/dashboard/socialops-dev"                          # 5  dashboard
  "$CW#alarmsV2:alarm/socialops-dev-api-5xx"                        # 6  alarm policy
  "$R/actions"                                                      # 7  pipeline runs
  "$R/actions/runs/42529005106"                                     # 8  good run (backup)
  "$R/actions/runs/42535888765"                                     # 9  failed + rollback run (backup)
  "https://us-east-1.console.aws.amazon.com/cloudshell/home?region=us-east-1"  # 10 CloudShell for terraform plan
)
for t in "${tabs[@]}"; do open "$t"; sleep 0.6; done
cat <<'TXT'

Tabs opened, left to right:
  1 app   2 API health   3 Logs Insights   4 Log group (Metric filters)   5 Dashboard
  6 Alarm 7 GitHub Actions   8 good run   9 failed/rollback run   10 CloudShell

Before you press record (off camera):
  [ ] Sign in to AWS and GitHub in the browser. Hide bookmarks and any personal tabs.
  [ ] Error route is OFF:   curl -s -o /dev/null -w "%{http_code}\n" https://api.socialops.website/debug/error   -> 404
  [ ] Alarm shows OK on tab 6. Nobody sends test requests.
  [ ] CloudShell warmed up (see docs/milestone6/handoff/DEMO_CUE_SHEET.md, step "Warm up").
  [ ] Cameras on for every presenter. No secrets, no .env, no email address on screen.

Then follow docs/milestone6/handoff/DEMO_CUE_SHEET.md from the top.
TXT

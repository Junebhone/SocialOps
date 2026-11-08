#!/usr/bin/env bash
# Controlled 5xx test for Milestone 6, run from AWS CloudShell.
# Switches the error route on (SSM), sends exactly ONE failing request, shows its
# JSON log line, the metric, the alarm going to ALARM (and the time it took), then
# switches the route off again and waits for the alarm to return to OK.
# The route is switched off on every exit path.
set -u
export AWS_PAGER=""
P=/socialops-dev/enable-error-route
API=https://api.socialops.website
LG=/ecs/socialops-dev/api
ALARM=socialops-dev-api-5xx
now() { date +%s; }
state() { aws cloudwatch describe-alarms --alarm-names "$ALARM" --query 'MetricAlarms[0].StateValue' --output text; }
off() { aws ssm put-parameter --name "$P" --type String --value false --overwrite >/dev/null && echo "route switched OFF at $(date -u +%T)Z"; }
trap off EXIT

echo "alarm state before: $(state)"
aws ssm put-parameter --name "$P" --type String --value true --overwrite >/dev/null && echo "route switched ON at $(date -u +%T)Z"

# The API reads the parameter on every request; wait until /debug/error stops being 404.
for i in $(seq 1 20); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$API/debug/error?kind=none" )
  [ "$code" != "404" ] && break; sleep 3
done
echo "route reachable (HTTP $code)"

RID="m6-test-$(now)"
T0=$(now)
echo "sending ONE failing request, request_id=$RID at $(date -u +%T)Z"
curl -s -o /dev/null -w "response: HTTP %{http_code}\n" -H "X-Request-ID: $RID" "$API/debug/error"
off   # route is off again right away; the one request is already counted

echo "--- JSON log line for $RID"
for i in $(seq 1 12); do
  L=$(aws logs filter-log-events --log-group-name "$LG" --filter-pattern "{ \$.request_id = \"$RID\" }" --query 'events[0].message' --output text)
  [ "$L" != "None" ] && { echo "$L"; break; }; sleep 5
done

echo "--- waiting for the metric and the alarm (can take 1-3 min)"
SUM=none
while [ $(( $(now) - T0 )) -lt 600 ]; do
  SUM=$(aws cloudwatch get-metric-statistics --namespace SocialOps/dev --metric-name Api5xxCount \
        --start-time "$(date -u -d '-10 min' +%FT%TZ)" --end-time "$(date -u -d '+1 min' +%FT%TZ)" \
        --period 60 --statistics Sum --query 'sum(Datapoints[].Sum)' --output text)
  S=$(state)
  echo "+$(( $(now) - T0 ))s  metric_sum_last10min=$SUM  alarm=$S"
  [ "$S" = "ALARM" ] && { echo ">>> ALARM reached $(( $(now) - T0 )) s after the request. Check the inbox for the alarm email now."; break; }
  sleep 10
done

echo "--- waiting for the alarm to return to OK (the OK email follows)"
while [ $(( $(now) - T0 )) -lt 1200 ]; do
  S=$(state); echo "+$(( $(now) - T0 ))s alarm=$S"
  [ "$S" = "OK" ] && { echo ">>> back to OK $(( $(now) - T0 )) s after the request."; break; }
  sleep 15
done
echo "done. route is OFF: $(aws ssm get-parameter --name "$P" --query Parameter.Value --output text)"

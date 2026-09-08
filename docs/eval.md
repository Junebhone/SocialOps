# Model eval log

Run `make eval` after any prompt or model change. 50 labeled comments in `data/eval.json`.

Sentiment is a 5-point integer (`-2..2`), so it is scored as mean absolute error, not accuracy.

| Date | Provider | Tier | Model | Category acc | needs_reply acc | Sentiment MAE | p50 latency (ms) | Cost / 100 comments |
|---|---|---|---|---|---|---|---|---|
| | ollama | fast | qwen3.5:2b | | | | | $0 |
| | ollama | standard | qwen3.5:9b | | | | | $0 |

## Why this table exists
The `fast` tier runs triage on a 2B model to keep the 2,000-comment replay inside a usable window
(D4). This table is the evidence that the small model did not cost us accuracy. If category accuracy
on `fast` drops below the `standard` baseline by more than a few points, promote triage to
`standard` and accept the slower drain.

It is also what makes ADR-0001's claim — that switching to Bedrock is an env change plus an eval
run — something you can actually demonstrate.

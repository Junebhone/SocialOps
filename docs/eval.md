# Model eval log

Run `make eval` after any prompt or model change. 50 labeled comments in `data/eval.json`.

Sentiment is a 5-point integer (`-2..2`), so it is scored as mean absolute error, not accuracy.

| Date | Provider | Tier | Model | Category acc | needs_reply acc | Sentiment MAE | p50 latency (ms) | Cost / 100 comments |
|---|---|---|---|---|---|---|---|---|
| 2026-09-09 | ollama | fast | qwen3.5:2b | 92% | 92% | 0.72 | 862 | $0 |
| 2026-09-09 | ollama | standard | qwen3.5:9b | 100% | 100% | 0.26 | 3550 | $0 |

Both rows: `prompts/triage.md` as of `ce93874`+, temperature 0, thinking disabled (D23),
50 labeled comments, 19 of them marked `hard`. Hard-case category accuracy was 17/19 on `fast`
and 19/19 on `standard`.

### Why temperature is pinned to 0 on the fast tier

The first two runs of this eval scored **82% and then 96% on an identical prompt**. At the
default temperature the sampler moves the number more than a prompt edit does, which makes the
table unable to answer the one question it exists to answer: did that change help? Classification
wants the argmax anyway. With `temperature=0` the same run reproduces exactly, and 92% is the
real figure — 96% was luck.

### The D4 tier question, answered

`fast` is **8 points behind** on category accuracy and more than twice as far off on sentiment.
D4 set the trigger at "more than a few points", so this is the signal it described. The
trade-off is not one-sided, and the arithmetic is in D4.

## Why this table exists
The `fast` tier runs triage on a 2B model to keep the 2,000-comment replay inside a usable window
(D4). This table is the evidence that the small model did not cost us accuracy. If category accuracy
on `fast` drops below the `standard` baseline by more than a few points, promote triage to
`standard` and accept the slower drain.

It is also what makes ADR-0001's claim — that switching to Bedrock is an env change plus an eval
run — something you can actually demonstrate.

---
name: agent-prompts
description: Conventions for writing or editing LLM agent prompt files in worker/agents/prompts/ and their Pydantic schemas. Use whenever touching a prompt or an agent's output contract.
---

# Agent prompt conventions

## File shape
- One Markdown file per agent: `worker/agents/prompts/<agent>.md`.
- Variables use `{{name}}` and are rendered by `worker/llm.py`. List every variable at the top in an HTML comment.
- Matching Pydantic model lives in `worker/agents/schemas.py`, named `<Agent>Output`.

## Writing rules (assume a 2B local model)
1. Start with one sentence of role + task. No "world-class", no personas.
2. Numbered rules, each one line. Max 8 rules.
3. Show the exact JSON schema with field types and allowed enum values. The prompt is the WHOLE
   contract — output mode is `PromptedOutput`, so there is no hidden tool schema to fall back on.
4. Give 2 few-shot examples: realistic input → exact JSON output. Cover one easy and one edge case (spam, non-English, emoji-only, sarcasm).
5. End with the literal line: `Respond with ONLY a JSON object. No markdown, no explanation.`
6. Never reference a provider feature (function calling, response_format, thinking). Portability over cleverness.
7. Keep total prompt under ~600 tokens excluding injected data.

## Template
```
<!-- variables: brand_voice, comment_text -->
You classify a social media comment for the brand's support team.

Rules:
1. category is one of: question, complaint, praise, spam, other.
2. sentiment is an integer: -2 hostile, -1 negative, 0 neutral, 1 positive, 2 delighted.
3. needs_reply is true for questions and complaints, false for spam.
4. urgency is high only for safety, legal, or refund threats.

Schema:
{"category": "question|complaint|praise|spam|other", "sentiment": 0, "needs_reply": true, "urgency": "low|med|high"}

Example 1
Comment: "Does this come in decaf??"
{"category":"question","sentiment":1,"needs_reply":true,"urgency":"low"}

Example 2
Comment: "🔥🔥🔥"
{"category":"praise","sentiment":2,"needs_reply":false,"urgency":"low"}

Comment: {{comment_text}}
Respond with ONLY a JSON object. No markdown, no explanation.
```

## Sentiment is an ordinal, never a float
Small models do not produce calibrated continuous scores — they echo whatever numbers appear in
the examples. Five buckets are also the only form a human can hand-label for `data/eval.json`.

## After any prompt change
- Run `make eval` (data/eval.json, 50 labeled comments) and report accuracy before/after.
- Update `docs/eval.md`.

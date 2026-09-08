# SocialOps — Claude Code Project Setup Guide

Goal: give Claude Code the right context and tools so it writes correct, consistent,
well-designed code — without drowning it in 40 plugins. Keep the toolset small. Every
skill/MCP you add costs context tokens on every session.

---

## 1. Repo skeleton for Claude Code

```
socialops/
  CLAUDE.md                     # rules (already written)
  .claude/
    settings.json               # permissions + hooks
    skills/                     # project skills (SKILL.md folders)
      frontend-design/
      tdd/
      code-review/
      agent-prompts/            # your own: JSON-output conventions for agents
    agents/                     # optional subagents
      reviewer.md
      tester.md
  .mcp.json                     # project-scoped MCP servers
  docs/
    DECISIONS.md                # running decision log — read this first
    PROMPTS.md
    START-HERE.md
    eval.md
    decisions/                  # ADRs (one file per decision)
```

Install order: CLAUDE.md → skills → MCP → hooks → subagents. Test after each; if Claude
Code starts ignoring rules or slowing down, you've added too much.

---

## 2. Skills (install 5, not 50)

Install from the ranked directory at claudeskills.info/skills or directly from the
source repos. Read each SKILL.md before installing — that's the whole point.

| Skill | Source | Why for SocialOps | Use in prompts |
|---|---|---|---|
| **frontend-design** | anthropics/skills | Dashboard that doesn't look like a Tailwind template. Palette, type, spacing. | Prompts 5, 7, 8 |
| **tdd** | mattpocock/skills | Red-green loop; keeps `TestModel` tests honest, prevents "tests that test nothing" | Prompts 1, 3, 4, 6 |
| **code-review** | mattpocock/skills | Reviews a diff against CLAUDE.md rules AND the spec. Run after every step. | After each prompt |
| **grill-me** | mattpocock/skills | Pressure-tests a plan before code. **Already run on Phase 1 — output is [DECISIONS.md](DECISIONS.md).** Run again before each later phase. | Before Prompt 0 |
| **diagnosing-bugs** | mattpocock/skills | Forces a reproducible failing command before theorizing. Saves hours on queue/async bugs. | When stuck |

Write your own **agent-prompts** skill (small):
```
.claude/skills/agent-prompts/SKILL.md
---
name: agent-prompts
description: How to write or edit an LLM agent prompt file in worker/agents/prompts/
---
- Prompts are Markdown with {{variables}}. No provider-specific syntax.
- Always end with: "Respond with ONLY a JSON object matching this schema:" + the schema.
- Include 2 short few-shot examples (good input → exact JSON).
- Assume a 2B local model: short instructions, numbered rules, no "you are a world-class…".
- The prompt is the whole contract — output mode is PromptedOutput, no hidden tool schema.
- Every prompt has a matching Pydantic schema in worker/agents/schemas.py.
- After editing a prompt, run `make eval` and paste the accuracy delta.
```

Skip for now: azure-* skills (Phase 2+ only if you go Azure), superpowers (too big),
caveman (fun, but it cuts explanations you'll need while learning).

---

## 3. MCP servers (install 3)

Put these in `.mcp.json` at repo root so every teammate gets them.

| MCP | Why | Notes |
|---|---|---|
| **Context7** (upstash/context7) | Live docs for Pydantic AI, `pydantic-graph`, arq, SQLAlchemy 2, Next.js 15 — all APIs that change often. Kills hallucinated method names. | Free tier is fine. Tell Claude "use context7" when it guesses an API. |
| **GitHub** (github/github-mcp-server) | Create issues from `to-tickets`, open PRs, read CI logs from Actions in Phase 6. | Use a fine-grained token scoped to the one repo. |
| **Postgres** — `googleapis/genai-toolbox` (MCP Toolbox for Databases) or the shadcn/`postgres-mcp` you prefer | Lets Claude inspect the schema and run read-only queries while debugging the pipeline. | Read-only credentials only. Point at the Docker Compose DB. |

Add in Phase 5/7 only: **Playwright MCP** (microsoft/playwright-mcp) or **Chrome DevTools
MCP** to let Claude click through the Inbox/Content pages and catch UI bugs itself.

Add in Phase 6 only: an AWS MCP (Terraform/CloudWatch) — not before.

Skip: browser-use, claude-flow, memory/knowledge-graph servers, anything write-capable
to external services. Trust boundary > tool count.

Example `.mcp.json`:
```json
{
  "mcpServers": {
    "context7": { "command": "npx", "args": ["-y", "@upstash/context7-mcp"] },
    "github":   { "command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"],
                  "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}" } }
  }
}
```
(Verify package names against each server's README — they change.)

---

## 4. Hooks (cheap, high value)

In `.claude/settings.json`, run lint/tests automatically so Claude sees failures without
you asking. Typical pattern:

- **After every file edit** (PostToolUse on Write/Edit): `ruff format` + `ruff check --fix`
  on Python files, `eslint --fix` on TS. Claude sees clean diffs.
- **Before commit**: `make test`. Commit is blocked if red.
- **On session start**: print `git status --short` and the last 3 commits so a fresh
  session knows where it is.

Check the Claude Code docs for the current hook syntax before writing these.

---

## 5. Subagents (optional, two are enough)

`.claude/agents/reviewer.md` — read-only; reviews the current diff against CLAUDE.md and
the step's prompt; reports violations, doesn't fix.
`.claude/agents/tester.md` — writes/extends tests only; may not touch non-test files.

Invoke: "Have the reviewer subagent check this diff before we commit."

---

## 6. Workflow per step

1. `/clear`
2. Paste the step prompt from PROMPTS.md.
3. Claude builds → hooks lint/test → Claude self-fixes.
4. "Run code-review on this diff." Fix findings.
5. Commit. Write a 5-line ADR in `docs/decisions/` if anything non-obvious was decided
   (e.g., "why arq instead of Celery"), and add a line to `docs/DECISIONS.md`.
6. Next step.

For big changes (Phase 4 decoupling, Phase 5 service split): `grill-me` on the plan
first, then `to-tickets` to cut it into one-context-window tasks, then `implement`.

---

## 7. Team hygiene

- One shared `CLAUDE.md`, `.mcp.json`, `.claude/settings.json` in git. Personal stuff in
  `.claude/settings.local.json` (gitignored).
- Everyone runs the same Ollama models (`make models` — two models, ~9.3 GB).
- Set `OLLAMA_MAX_LOADED_MODELS=2` and `OLLAMA_KEEP_ALIVE=30m` on the host, not in a container.
- Keep the `docs/eval.md` table current: provider, tier, model, category accuracy,
  needs_reply accuracy, sentiment MAE, p50 latency, cost per 100 comments. Update whenever a
  prompt or a model changes. This becomes a slide.
- Weekly: run `improve-codebase-architecture` (mattpocock) once, act on 1–2 items, ignore
  the rest. Don't let it refactor everything.

---

## What NOT to install
- More than one design skill (they fight).
- Any skill that rewrites how Claude responds globally (caveman, personas).
- MCPs with write access to Slack/Gmail/social platforms — out of scope and risky.
- "Swarm"/multi-agent orchestration MCPs. Your project already IS the multi-agent system.

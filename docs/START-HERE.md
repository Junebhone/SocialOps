# START HERE — SocialOps Phase 1 with Claude Code

Follow top to bottom. ~45 minutes before the first build prompt.

## 0. Prerequisites (each teammate)
- Docker Desktop — **cap its memory explicitly** (Settings → Resources → ~4 GB). Left at the
  default it will compete with Ollama for RAM.
- Node 20+, Python 3.12+, `jq`, `make`, `git`
- Ollama installed and running: https://ollama.com
- **16 GB RAM minimum.** Two models stay resident (~9.3 GB); see D19 in
  [DECISIONS.md](DECISIONS.md). Set these on the host shell, not in a container:
  ```
  OLLAMA_MAX_LOADED_MODELS=2
  OLLAMA_KEEP_ALIVE=30m
  ```
- ~10 GB free disk for the models
- Claude Code installed and logged in: https://docs.claude.com/en/docs/claude-code/overview
- A GitHub fine-grained token with read/write on this one repo, exported as `GITHUB_TOKEN`

## 1. Create the repo
    unzip socialops-kit.zip && cd socialops
    git init
    cp .env.example .env
    make models          # pulls qwen3.5:2b and qwen3.5:9b (~9.3 GB)
    git add -A && git commit -m "chore: bootstrap kit"

Push to a private GitHub repo so teammates can clone.

## 2. Install skills
Open Claude Code in the repo folder and paste:

    Read docs/SETUP.md section 2. Install these skills into .claude/skills/ from their
    public source repos, keeping each one's original SKILL.md: frontend-design
    (anthropics/skills), and tdd, code-review, grill-me, diagnosing-bugs
    (mattpocock/skills). The agent-prompts skill already exists — leave it. Then run
    `ls -R .claude/skills` and show me the tree. Do not modify CLAUDE.md.

If a skill has moved, ask Claude to search claudeskills.info for the current path.

## 3. Verify MCP
Restart Claude Code in the folder (it loads .mcp.json on start), then run `/mcp`.
You should see context7 and github connected. If github fails, make sure GITHUB_TOKEN is
exported in the shell you launched Claude Code from.

## 4. Sanity-check hooks
Ask Claude: "Create scratch.py with badly formatted code, show it, then delete it."
The PostToolUse hook formats it on write. If ruff isn't on the host yet this silently
no-ops — fine until Prompt 0 installs the toolchain.

## 5. Read the decision log
**This step is already done.** `/grill-me` was run against the Phase 1 plan and produced
[DECISIONS.md](DECISIONS.md) — 19 decisions with reasoning, plus ADRs 0002 and 0003.
`CLAUDE.md` has been updated to match.

Read it before Prompt 0. It explains why the schema, the model tiers, and the orchestration
look the way they do, and it names the two assumptions the plan rests on. Re-run `/grill-me`
before each later phase, not before each step.

## 6. Build
For each step in docs/PROMPTS.md:
1. `/clear`
2. Paste the step prompt.
3. When it finishes: "Run the reviewer subagent on the diff." Fix BLOCKERs.
4. Confirm the commit happened (the pre-commit hook runs make test when containers are up).
5. If a non-obvious decision was made, copy docs/decisions/0000-template.md to a new ADR.

Rules of thumb:
- One prompt per /clear. Long contexts make Claude Code sloppy.
- If a step goes wrong, don't paste the next prompt. Say: "Step N failed at X. Use the
  diagnosing-bugs skill, fix it, run make test, then stop."
- If Claude guesses an API, say: "Use context7 to check the real signature." This matters most
  for Pydantic AI and `pydantic-graph`, which are new enough that a model may invent methods.
- Never let it read .env (the deny rule enforces this).
- If a step's output contradicts docs/DECISIONS.md, that's a bug in the step, not the log.

## 7. Team split
The plan assumes an **effectively solo build** (D1). Steps run in order; there is no split,
because steps 4–8 all depend on 0–3 and parallelising them mostly produces merge conflicts.

Work on a branch per step, run the reviewer subagent before each merge, and keep main green
(`make test` and `make lint`).

**If teammates do have time**, the two tasks that parallelise cleanly with zero conflicts:
- Hand-label the 50 comments in `data/eval.json` (step 2). One hour, no code.
- Write the comment templates and brand voice guidelines for `data/seed.py` (step 2).

If the team situation changes, D1 is the first entry to revisit — nothing else depends on it.

## 8. Weekly
- `make eval` → update docs/eval.md
- Skim `git log`, write any missing ADRs, add a line to docs/DECISIONS.md
- Delete merged branches, keep main green

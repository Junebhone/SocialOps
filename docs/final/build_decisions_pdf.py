"""Build docs/final/SocialOps-design-decisions.pdf from the decision log.

usage: python3 docs/final/build_decisions_pdf.py   (needs Google Chrome)
Sources: docs/DECISIONS.md (D1-D36), docs/decisions/ (ADRs), milestone analyses.
"""

import html
import pathlib
import subprocess

HERE = pathlib.Path(__file__).parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# (milestone, subtitle, intro, [cards]); card = (ref, title, decision, why, rejected, evidence)
MILESTONES = [
    (
        "Milestone 1",
        "Working local app",
        "Docker Compose on one laptop: FastAPI, Next.js, Postgres, Redis, a worker, and local "
        "models through Ollama. The aim was to build the app correctly from the start, so every "
        "later milestone changes the infrastructure underneath it, not the app.",
        [
            ("D2", "Stateless from day one; the migration is re-platforming",
             "The API holds no state, the worker is a separate container, and work goes through a "
             "Redis queue from the first commit. The later phases are described as moving the "
             "same app onto managed services, not as rewriting it.",
             "The proposal promised a stateful monolith to fix later. Building bad architecture on "
             "purpose is real work that produces nothing, and it would have left the later phases "
             "with nothing to do. Being honest about it was cheaper and easier to defend.",
             "Write throwaway in-memory state so there is something to remove later.",
             "Every later move (VM, ECS, RDS, S3, EKS, Bedrock) changed environment variables, not code."),
            ("D1", "Cut the analytics dashboard; keep the photo-to-posts flow",
             "Ship the inbox, approvals, the photo upload that writes three platform posts, the "
             "load replay and the failed-jobs queue. Cut the analytics agent and its chart to a "
             "plain table of agent runs.",
             "Uploading one photo and watching three drafts appear is the most striking thing the "
             "product does. The analytics agent writes a paragraph nobody reads on stage. The "
             "agent-runs table is kept because it is the audit trail and the cost dashboard.",
             "Cutting the content page together with analytics, which would have removed the best demo moment.",
             None),
            ("D3", "The approval loop actually closes",
             "Reply drafts record who approved them, when, and a published state. An outbox table "
             "is drained by the worker, so an approved reply visibly goes out.",
             "The pitch is that a person approves everything before it publishes. Without a "
             "published state, Approve would have left rows stuck forever. The outbox is also the "
             "exact place a real platform integration would plug in later.",
             None, None),
            ("ADR-0002 / D11, D13", "Pydantic AI for every model call; LangGraph and LiteLLM removed",
             "All model access goes through Pydantic AI, with one function, complete(), as the "
             "single place a model is called. It times the call, validates the output and records "
             "tokens and cost.",
             "The project is Pydantic end to end, and Pydantic AI already does validation, retries "
             "and provider switching (Ollama locally, Bedrock in AWS). LiteLLM would have meant a "
             "second retry loop and an extra proxy container. Pydantic AI also ships test models, "
             "so no test can call a real model.",
             "ADR-0001 (LiteLLM behind a hand-written wrapper), superseded the same day.",
             None),
            ("ADR-0003 / D12", "A typed graph orchestrates; routing is an if, not a model decision",
             "The orchestrator is a pydantic-graph graph: ingest, triage, response if a reply is "
             "needed, persist. No durable-execution framework, and no agent calling another agent.",
             "A typed graph is about 45 more lines than a plain function and gives typed state, a "
             "generated diagram, and a direct mapping to AWS Step Functions later. Letting a 2B "
             "model decide control flow would make routing random and unauditable.",
             "LangGraph (oversized for one branch); Temporal or DBOS (a second retry system on top of arq); "
             "pausing the run for approval (approval arrives days later over HTTP).",
             None),
            ("D6", "Agents name a tier, never a model",
             "Every agent declares fast, standard or vision. Configuration maps the tier to a "
             "model: Qwen on Ollama locally, Claude on Bedrock in AWS.",
             "This is what makes switching provider a one-line environment change. It also gives "
             "the cost dashboard spend per tier for free.",
             "A per-agent model map in JSON: more flexible than needed, and a typo becomes a runtime crash.",
             "Moving to Bedrock in Milestones 5 and 6 changed no agent and no prompt."),
            ("D4, D20", "Small model for triage, larger model for drafting",
             "qwen3.5:2b for triage and qwen3.5:9b for replies, content and vision. Two models "
             "cover three tiers because the 9B model also reads images.",
             "One laptop is memory-bound. Triage is a simple classification, and moving it to the "
             "small model cut the triage leg of a 2,000-comment run from about 66 minutes to 13. "
             "27B models were rejected because they do not fit in 16 GB and would swap to disk.",
             "qwen3.6:8b, the model first specified, which turned out not to exist.",
             "Measured: triage about 850 ms, a reply draft about 3.4 s."),
            ("D5, D8", "An eval set, and sentiment as five buckets",
             "50 hand-labelled comments in data/eval.json, scored by make eval. Sentiment is an "
             "integer from -2 to 2, not a float.",
             "Without an eval, nothing shows that a smaller model or a prompt change kept accuracy. "
             "Small models do not produce calibrated decimals, and a person cannot hand-label a "
             "float, but five buckets they can.",
             None, "qwen3.5:9b scored 100% category accuracy, sentiment error 0.26."),
            ("D14, D23", "Schema in the prompt, and thinking switched off",
             "Agents use prompted JSON output checked against a schema, with up to 3 retries. "
             "Qwen's reasoning mode is turned off on every local call.",
             "Tool calling is unreliable on a 2B model. With thinking on, both models spent their "
             "whole output budget reasoning and returned nothing. Only one of three ways to turn it "
             "off worked through Ollama's endpoint, and we found that by testing all three.",
             None, None),
            ("D7, D15", "Every agent run is one auditable row with an honest cost",
             "Each agent call writes one agent_runs row: tokens, latency, cost, and a joinable "
             "reference to the comment or asset that caused it. Cost is 0 for local models, the "
             "real price when known, and empty when it cannot be priced.",
             "This is the audit trail and the cost dashboard in one table. Showing an unknown "
             "price as $0.00 would make Bedrock look free whenever a price lookup missed.",
             "An opaque text reference that cannot be joined.", None),
            ("D9, D27, D29", "Ingest is idempotent, rejects bad rows, and locks against races",
             "Comments are unique per post, so a replay never double-charges. A bad row goes "
             "straight to the failed-jobs table while the rest are processed. The worker locks the "
             "comment row before working on it.",
             "The 2,000-comment test file has one bad row on purpose. The first version rejected "
             "the whole batch and processed zero comments. The load replay also found one comment "
             "triaged twice; the row lock fixed the race and a unique constraint backs it up.",
             None, "Race seen in 1 of 300 comments, then fixed and covered by a concurrency test."),
            ("D25", "Storage is one interface: local disk now, S3 later",
             "Files go through StorageBackend (put, get, url, delete). It is async even though "
             "local disk does not need it.",
             "S3 is network I/O. An async interface from the start meant S3 support later changed "
             "no call sites, which is exactly what happened.",
             "Two separate storage implementations in the API and the worker, which would drift.", None),
            ("D28", "Liveness and readiness are different questions",
             "/health only says the process is up. /health/ready checks Postgres and Redis and "
             "returns 503 when either is down.",
             "During development the database died while every health check stayed green. A "
             "liveness check that depends on the database would restart the app for someone "
             "else's outage. Kubernetes and the deploy pipeline later used both endpoints by name.",
             None, "Later became the signal the Milestone 6 pipeline uses to roll back."),
            ("D17, ADR-0005", "Brand in the URL; analytics computed live",
             "brand_id is a required query parameter on every list endpoint. Analytics are plain "
             "SQL over the source tables, with no cache.",
             "Auth was out of scope, but showing one brand's comments in another's view would be "
             "the worst demo moment. Keeping state in the URL and out of memory keeps the API "
             "stateless, so any copy of it can answer any request.",
             None, None),
        ],
    ),
    (
        "Milestone 2",
        "Platform setup and lift-and-shift",
        "The same app moved by hand onto one EC2 virtual machine, plus the first Terraform and CI "
        "for the AWS target.",
        [
            ("M2", "Install everything natively on one VM",
             "One m7i-flex.large Ubuntu VM in us-east-2 with an Elastic IP. Python, Node, Postgres "
             "16, Redis 7 and Ollama were installed directly, with no Docker.",
             "The brief graded installing the runtimes and starting the processes ourselves. A "
             "plain lift-and-shift also gives a clear baseline for every later step.",
             "t3.large, which the free plan refused.",
             "The app ran on the VM with the small local model pair (D31)."),
            ("M2", "Firewall by allowlist, with a budget",
             "The security group allows SSH only from the team's own IP addresses (/32 rules). "
             "An AWS budget alert guards spending.",
             "Least privilege from the first server: nothing is open to the internet that does "
             "not need to be.", None, None),
            ("D34", "Ollama stays on the host, outside the containers",
             "Containers reach Ollama on the host machine through host.docker.internal.",
             "A containerised Ollama would be a multi-gigabyte CPU image that re-ships the model "
             "weights on every rebuild and competes with Postgres for memory. The code already "
             "treats Ollama as an external URL, which Bedrock later replaced.",
             None, None),
            ("ADR-0006 / D32", "Terraform in two roots, planned in CI, no stored keys",
             "A bootstrap root holds what exists once per account: the state bucket, the lock "
             "table, the image registry and the CI roles. A stack root holds one environment per "
             "workspace (dev, staging). Every pull request runs lint, tests and terraform plan. "
             "GitHub signs in to AWS through OIDC.",
             "Plans can be checked without spending money, the two environments cannot be mixed "
             "up (a guard refuses a mismatched workspace and tfvars), and there are no long-lived "
             "AWS keys anywhere in GitHub.",
             "One root for everything, which would make the state bucket depend on itself.",
             "Images are built once per merge, tagged with the commit SHA, and promoted by tag."),
        ],
    ),
    (
        "Milestone 3",
        "Containerize",
        "Production-shaped images and a registry, so the laptop, the VM and the cloud run the same artifact.",
        [
            ("D33", "Multi-stage images; the runtime stage is the default",
             "Each Dockerfile has a dependency stage, a dev stage and a slim runtime stage that "
             "runs as a non-root user. Development hot-reload is an opt-in override file.",
             "Before this, the cloud was running the development image, with test tools inside "
             "and the web app rebuilding itself on every start. Splitting stages made images "
             "smaller and means the image CI builds is the one that runs.",
             None, "api 432 to 275 MB, worker 528 to 423 MB, web 993 to 246 MB."),
            ("D33", "Secrets never enter an image",
             "No stage copies .env, and every build context excludes it with .dockerignore. "
             "Secrets are passed at runtime.",
             "The worker's build context had no .dockerignore before, so .env and .git were being "
             "sent to the builder.", None, None),
            ("D35", "Registry tags: v1 for proof, v2 for real shipping",
             "v1 is amd64 only, so the laptop and the VM run byte-identical images. v2 is "
             "multi-arch, so each machine pulls the image built for its own CPU.",
             "v1 proves the milestone's goal literally (same digest everywhere). v2 is how you "
             "would actually ship. Tags are never re-pushed.",
             None, None),
        ],
    ),
    (
        "Milestone 4",
        "Decouple state",
        "Data and files moved off the VM into managed services.",
        [
            ("M4", "Postgres moves to Amazon RDS, checked by row counts",
             "The VM database was migrated to RDS using a schema snapshot and a migration script, "
             "with row counts taken for every table before and after.",
             "Row counts on all 13 tables are simple, repeatable evidence that nothing was lost.",
             None, "scripts/row_counts.sql and api/alembic/sql/schema_head.sql."),
            ("D25", "Uploads move to S3 with no call-site changes",
             "S3Storage is the second implementation of the storage interface, chosen by "
             "STORAGE_BACKEND=s3. Signing is pinned to SigV4, the region comes from config, and "
             "only a missing file becomes a not-found error.",
             "The interface built in Milestone 1 paid off: nothing that uses storage changed. "
             "Access-denied and throttling errors are left to the job queue to retry instead of "
             "being treated as a missing image.",
             None, None),
            ("M4", "Synthetic data is reseeded, not migrated, between regions",
             "When the stack later moved to us-east-1, the database was seeded fresh.",
             "All data is synthetic, so reseeding is faster and safer than copying a database "
             "across regions.", None, None),
        ],
    ),
    (
        "Milestone 5",
        "Orchestrate on Kubernetes",
        "The same images on Amazon EKS, with the models moved from a laptop to Amazon Bedrock.",
        [
            ("D36", "EKS for the milestone; the pods call Bedrock",
             "api, web and worker run as Deployments on a two-node EKS cluster in us-east-2, in "
             "the same network as RDS. The worker calls Bedrock (Nova Micro and Nova Lite).",
             "Pods cannot reach Ollama on a laptop, and Bedrock was always the planned cloud "
             "provider. Thanks to tiers, the switch was one code branch and three config values; "
             "no prompt changed.",
             None, "Cluster cost about $6 a day, so it was created for the demo and torn down after."),
            ("M5", "Pods get AWS access through IRSA, never key files",
             "A dedicated IAM role is attached to the service account, with a policy limited to "
             "what the pods use.", "Short-lived credentials, scoped per workload.", None, None),
            ("M5", "Survive node drains: PDBs, spread, probes",
             "Two replicas of api and web, one per node. A PodDisruptionBudget keeps at least one "
             "running, rolling updates never take a pod away first, a 10-second pause before "
             "shutdown, and readiness on /health/ready.",
             "Without a disruption budget, draining a node can evict every replica at once and "
             "users see scattered 502 and 503 errors.",
             "A budget on the single worker and Redis pods, which would block every drain.",
             "Drained both nodes under load: 337 of 360 requests OK; Kubernetes refused to evict the last pod."),
            ("M5", "Images pinned by digest", "Manifests reference images by digest, not tag.",
             "The cluster runs exactly the bytes that were tested.", None, None),
        ],
    ),
    (
        "Milestone 6",
        "Observe and automate",
        "Everything in Terraform on ECS Fargate in us-east-1, with HTTPS, monitoring, alerting and "
        "a pipeline that deploys and rolls back on its own.",
        [
            ("M6", "ECS Fargate instead of EKS",
             "The final platform is ECS Fargate: three services behind an Application Load "
             "Balancer, in private subnets across two availability zones.",
             "We ran both. EKS earned its keep for disruption budgets and autoscaling, but it adds "
             "a control plane to pay for and operate. Three services do not need it.",
             "Keep EKS (more to run); Lambda (LLM calls run for tens of seconds and need a long-lived queue consumer).",
             None),
            ("M6", "The whole stack in Terraform, with listed exceptions",
             "Network, load balancer with HTTPS, ECS, RDS, Redis, S3, SQS, IAM, logs, alarm, "
             "dashboard and SNS are all Terraform. Pipeline deploys are not treated as drift.",
             "The stack can be rebuilt from scratch. A few things stay outside on purpose: the "
             "state bucket (needed before Terraform runs), the DNS zone, the budget, Bedrock "
             "model access and the email confirmation click.",
             None, "terraform plan after three pipeline deploys: No changes."),
            ("M6", "HTTPS on our own domain",
             "Route 53 and an ACM certificate on the load balancer; port 80 redirects to 443.",
             "A real address with a padlock is the minimum for anything a customer touches.",
             None, None),
            ("M6", "Logs become a metric, the metric becomes an alarm",
             "One JSON log line per request. A CloudWatch filter counts lines with status 500 or "
             "above, an alarm fires on one in a minute, and SNS emails the team.",
             "Failures reach us before a customer reports them. Unhandled exceptions are logged "
             "with a 500 too, so crashes count. A quiet minute is not treated as a failure.",
             None, "Controlled error at 23:52:15 UTC; alarm email about a minute later."),
            ("M6", "The pipeline rolls back what ECS cannot see",
             "Every push to main: lint and test, build images tagged with the commit, run the "
             "migration as a one-off task, deploy, then check /health/ready and the web page. If "
             "a check fails, restore the previous versions, prove they serve, and fail the run.",
             "The ECS circuit breaker only rolls back tasks that never start. Our check also "
             "catches a version that starts but is unhealthy. A failed migration stops the deploy "
             "before any service changes.",
             None, "Good run 42529005106; deliberate bad deploy 42535888765 rolled back automatically."),
            ("M6", "Claude on Bedrock for the final stack",
             "Claude Haiku for triage, Claude Sonnet for replies, content and vision, through "
             "Bedrock inference profiles.",
             "Same tier switch as Milestone 5: configuration only. Pay per token, no GPU to own.",
             None, None),
            ("M6", "Dev is cheap on purpose, and production is a settings change",
             "Dev runs one task per service, single-AZ RDS, one NAT gateway and 1-day backups. "
             "The modules already accept the production values.",
             "About $5 a day for dev. Multi-AZ, more tasks and longer backups are existing "
             "Terraform variables, not new work.",
             None, None),
        ],
    ),
]

PRODUCTION = [
    ("Availability", "1 task per service, single-AZ RDS, 1 NAT", "2+ tasks across AZs, Multi-AZ RDS, NAT per AZ, Redis replica"),
    ("Scaling", "Fixed task counts (autoscaling proven on EKS)", "Scale the API on CPU and the worker on queue depth"),
    ("Data safety", "1-day backups, disposable", "7 to 35 days with point-in-time restore, deletion protection, cross-region copies"),
    ("Security", "Private DB, OIDC, Secrets Manager, S3 public-access block", "User sign-in, WAF and rate limits, restricted ingress, per-brand tenancy"),
    ("Deploys", "Rolling deploy with health-check rollback", "Blue/green or canary, staging with manual promotion, expand/contract migrations"),
    ("Observability", "5xx metric, alarm, dashboard, email", "SLOs, tracing across agents, paging, queue-age and LLM-cost alarms"),
    ("LLM", "Bedrock, 3 retries, failed-jobs table", "Guardrails, eval as a CI gate, per-brand token budgets, fallback model"),
    ("Cost", "About $5/day, budget alert", "Savings Plans, Graviton, workers scaled to zero overnight"),
]

REVERSED = [
    ("LiteLLM for model access (ADR-0001)", "Replaced by Pydantic AI the same day: one framework, one retry loop."),
    ("LangGraph for orchestration (D10)", "Replaced by pydantic-graph: a typed graph sized for one branch."),
    ("qwen3.6:8b as the main model", "The tag does not exist; replaced by qwen3.5:9b after checking the library."),
    ("A stateful monolith in Phase 1", "Built stateless instead; the roadmap was reworded (D2)."),
    ("Retry on every failed job (D30)", "A malformed row can never succeed, so those rows get Discard instead."),
    ("EKS as the final platform", "Moved to ECS Fargate in Milestone 6 for lower cost and less to operate."),
]


def e(s):
    return html.escape(s or "")


def card(ref, title, decision, why, rejected, evidence):
    rows = [f'<p><b>Decision.</b> {e(decision)}</p>', f'<p><b>Why.</b> {e(why)}</p>']
    if rejected:
        rows.append(f'<p class="alt"><b>Rejected.</b> {e(rejected)}</p>')
    if evidence:
        rows.append(f'<p class="ev"><b>Evidence.</b> {e(evidence)}</p>')
    return f'<div class="card"><div class="ref">{e(ref)}</div><h3>{e(title)}</h3>{"".join(rows)}</div>'


def build():
    journey = "".join(
        f"<tr><td><b>{e(m)}</b></td><td>{e(sub)}</td><td>{len(cards)}</td></tr>"
        for m, sub, _, cards in MILESTONES
    )
    sections = "".join(
        f'<section class="ms"><div class="kicker">{e(m)}</div><h2>{e(sub)}</h2>'
        f'<p class="intro">{e(intro)}</p>{"".join(card(*c) for c in cards)}</section>'
        for m, sub, intro, cards in MILESTONES
    )
    prod = "".join(f"<tr><td><b>{e(a)}</b></td><td>{e(b)}</td><td>{e(c)}</td></tr>" for a, b, c in PRODUCTION)
    rev = "".join(f"<tr><td>{e(a)}</td><td>{e(b)}</td></tr>" for a, b in REVERSED)
    total = sum(len(c) for *_, c in MILESTONES)
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>SocialOps design decisions</title>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,500;6..72,600&family=Public+Sans:wght@400;600;700&family=Geist+Mono:wght@500&display=swap" rel="stylesheet">
<style>
@page{{size:Letter;margin:0.7in 0.75in}}
:root{{--ink:#2c2723;--mut:#6b625a;--acc:#b0532c;--line:#e6dccf;--soft:#f6efe5}}
body{{font:10pt/1.5 'Public Sans',sans-serif;color:var(--ink);margin:0}}
h1,h2,h3{{font-family:Newsreader,serif;font-weight:600;margin:0}}
.cover{{height:9.4in;display:flex;flex-direction:column;justify-content:center;page-break-after:always}}
.cover .kicker{{margin-bottom:14px}}
.cover h1{{font-size:44pt;line-height:1.05;margin-bottom:18px}}
.cover p{{font-size:12.5pt;color:var(--mut);max-width:5.4in}}
.cover .meta{{margin-top:40px;font-size:10pt;border-top:1px solid var(--line);padding-top:14px}}
.kicker{{font:500 8.5pt 'Geist Mono',monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--acc)}}
h2{{font-size:22pt;margin:4px 0 6px}}
.ms{{page-break-before:always}}
.intro{{color:var(--mut);margin:0 0 14px;max-width:6.2in}}
.card{{border-left:3px solid var(--acc);background:var(--soft);padding:9px 14px 4px;margin:0 0 10px;break-inside:avoid}}
.card h3{{font-size:12.5pt;margin:1px 0 4px}}
.card p{{margin:0 0 5px}}
.ref{{font:500 8pt 'Geist Mono',monospace;color:var(--acc)}}
.alt,.ev{{font-size:9.2pt;color:var(--mut)}}
table{{width:100%;border-collapse:collapse;font-size:9.4pt;margin:8px 0 14px}}
th{{text-align:left;font-weight:700;border-bottom:1.5px solid var(--ink);padding:5px 6px}}
td{{border-bottom:1px solid var(--line);padding:6px;vertical-align:top}}
.big{{font-family:Newsreader,serif;font-size:15pt;line-height:1.35;margin:10px 0 16px;max-width:6.3in}}
.page{{page-break-before:always}}
ol.principles li{{margin-bottom:6px}}
</style></head><body>
<div class="cover"><div class="kicker">EDS 6348 · Group 5 · Final</div>
<h1>SocialOps<br>Design decisions</h1>
<p>Every design decision from Milestone 1 to Milestone 6: what we chose, why, what we rejected, and the evidence that it worked.</p>
<div class="meta">{total} decisions across six milestones · Source: docs/DECISIONS.md (D1 to D36), ADR-0001 to ADR-0006 and the milestone analyses · November 2026</div></div>

<div class="kicker">Overview</div><h2>One idea behind every choice</h2>
<p class="big">Build the app correctly once, then move it to better infrastructure without rewriting it.</p>
<p>SocialOps is a multi-agent command center for small-business social media. Agents triage every comment and draft replies and posts; a person approves everything before it goes out. It started on a laptop and ended on AWS. Four rules from Milestone 1 made every later move a configuration change instead of a rewrite:</p>
<ol class="principles">
<li><b>Config comes only from environment variables</b>, read in one place per service.</li>
<li><b>The API holds no state</b>, so any copy of it can answer any request.</li>
<li><b>Storage and models sit behind interfaces</b>: StorageBackend for files, model tiers for LLMs.</li>
<li><b>Every agent call is one audited row</b> with tokens, cost and latency.</li>
</ol>
<table><tr><th>Milestone</th><th>What changed</th><th>Decisions</th></tr>{journey}</table>
<p><b>Final architecture.</b> Browser → Route 53 → ALB (HTTPS) → ECS Fargate (web, api) in private subnets over two zones → RDS Postgres and ElastiCache Redis → worker → Amazon Bedrock and S3. Secrets Manager injects config; CloudWatch logs feed a 5xx alarm that emails the team. GitHub Actions deploys through OIDC and rolls back automatically.</p>
{sections}
<div class="page"><div class="kicker">Beyond the course</div><h2>What we would change for production at full scale</h2>
<p class="intro">Most of this is a tfvars change: the Terraform modules already take these switches, and dev picks the cheapest values.</p>
<table><tr><th>Area</th><th>Dev today (proven)</th><th>Production</th></tr>{prod}</table>
<div class="kicker" style="margin-top:18px">Changed our minds</div><h2>Decisions we reversed, and why</h2>
<p class="intro">Each of these was replaced when evidence showed a better option. The log keeps the old entry marked superseded.</p>
<table><tr><th>Original choice</th><th>What replaced it</th></tr>{rev}</table></div>
</body></html>"""


if __name__ == "__main__":
    src = HERE / "design-decisions.html"
    out = HERE / "SocialOps-design-decisions.pdf"
    src.write_text(build())
    subprocess.run([CHROME, "--headless=new", "--no-pdf-header-footer", "--virtual-time-budget=8000",
                    f"--print-to-pdf={out}", src.resolve().as_uri()], check=True, capture_output=True)
    print(f"wrote {out}")

# ruff: noqa
"""Build Milestone6_SocialOps.pptx. Placeholders are labelled [SCREENSHOT: ...] / [TODO ...]."""
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

INK, MUTED, ACCENT, PANEL, WARN = (RGBColor(0x1F,0x29,0x37), RGBColor(0x6B,0x72,0x80),
    RGBColor(0x25,0x63,0xEB), RGBColor(0xF3,0xF4,0xF6), RGBColor(0xB4,0x53,0x09))
prs = Presentation(); prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
blank = prs.slide_layouts[6]

def text(sl, x, y, w, h, s, size=18, bold=False, color=INK, align=PP_ALIGN.LEFT, font="Calibri"):
    tb = sl.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf = tb.text_frame; tf.word_wrap = True
    for i, line in enumerate(s if isinstance(s, list) else [s]):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align; r = p.add_run(); r.text = line
        r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(size), bold, color, font
        p.space_after = Pt(6)
    return tb

def slide(title, sub=None):
    sl = prs.slides.add_slide(blank)
    text(sl, 0.6, 0.35, 12, 0.8, title, 32, True)
    if sub: text(sl, 0.6, 1.1, 12, 0.5, sub, 16, color=MUTED)
    return sl

def bullets(sl, items, x=0.6, y=1.8, w=12, size=20):
    text(sl, x, y, w, 5, ["•  " + i for i in items], size)

def box(sl, x, y, w, h, label, fill=PANEL, color=INK, size=13, line=None):
    s = sl.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid(); s.fill.fore_color.rgb = fill
    s.line.color.rgb = line or RGBColor(0xD1,0xD5,0xDB)
    tf = s.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER; r = p.add_run(); r.text = label
    r.font.size, r.font.color.rgb, r.font.name = Pt(size), color, "Calibri"
    return s

def arrow(sl, x1, y1, x2, y2):
    c = sl.shapes.add_connector(1, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = MUTED; c.line.width = Pt(1.75)
    ln = c.line._get_or_add_ln()
    from lxml import etree
    ln.append(etree.SubElement(ln, "{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd", type="triangle"))

def placeholder(sl, label, x=0.6, y=1.8, w=12, h=4.9):
    s = box(sl, x, y, w, h, f"[SCREENSHOT: {label}]", RGBColor(0xFE,0xF3,0xC7), WARN, 20, WARN)

# 1 title
sl = prs.slides.add_slide(blank)
text(sl, 0.8, 2.3, 12, 1.2, "SocialOps: observability and automated deployment", 40, True)
text(sl, 0.8, 3.7, 12, 0.6, "Milestone 6, EDS 6348 Intro to Cloud Computing, University of Houston", 20, color=MUTED)
text(sl, 0.8, 4.6, 12, 1.2, ["Group 5", "Dan (Terraform, HTTPS)   Zainab (logging, 5xx metric)   Tan (dashboard, alerting, CI/CD, analysis)",
     "[TODO: confirm full team list and names]"], 16, color=MUTED)

# 2 architecture
sl = slide("Architecture: monitoring and deployment", "Live at https://app.socialops.website  |  API health at https://api.socialops.website/health/ready")
row1 = [("GitHub Actions\n(build, deploy)",0.6),("ECR\n(images by SHA)",3.0),("ECS Fargate\napi · web · worker",5.4),("ALB + HTTPS\n(ACM cert)",7.8),("Users",10.2)]
for lbl,x in row1: box(sl,x,2.0,2.0,1.0,lbl,size=14)
for a,b in [(2.6,3.0),(5.0,5.4),(7.4,7.8),(9.8,10.2)]: arrow(sl,a,2.5,b,2.5)
row2 = [("CloudWatch Logs\n(JSON per request)",0.6),("Metric filter\nApi5xxCount",3.0),("Alarm\nSum ≥ 1 / 60 s",5.4),("SNS topic",7.8),("Team email",10.2)]
for lbl,x in row2: box(sl,x,4.3,2.0,1.0,lbl,RGBColor(0xDB,0xEA,0xFE),size=14)
for a,b in [(2.6,3.0),(5.0,5.4),(7.4,7.8),(9.8,10.2)]: arrow(sl,a,4.8,b,4.8)
arrow(sl,6.4,3.0,1.6,4.3)
text(sl,6.2,3.4,3.5,0.4,"stdout → logs",12,color=MUTED)
for lbl,x in [("RDS (private)",0.6),("Redis",3.0),("S3 (IAM role)",5.4),("SQS",7.8),("Secrets Manager",10.2)]: box(sl,x,6.0,2.0,0.7,lbl,size=13)
text(sl,0.6,5.5,6,0.4,"Data and secrets plane",13,color=MUTED)

# 3 logging
sl = slide("Logging: one JSON line per request", "structlog in api/app/logging.py; every line carries request_id")
box(sl,0.6,1.9,12,1.9,'{"event": "request", "method": "GET", "path": "/health/ready", "status_code": 200, "duration_ms": 4.1,\n "request_id": "<32 hex>", "level": "info", "timestamp": "<ISO-8601 UTC>"}',RGBColor(0x11,0x18,0x27),RGBColor(0xE5,0xE7,0xEB),14)
bullets(sl,["Fields and shape are from the code. [TODO: replace with one real line from the live log group, secrets checked]",
            "Unhandled exception → event request.failed with status_code=500, so crashes are counted",
            "Inbound X-Request-ID is honoured, so a request can be traced end to end"],y=4.1,size=18)

# 4 metric
sl = slide("Log-based metric: counting HTTP 5xx")
bullets(sl,["Log group: /ecs/socialops-dev/api",
            "Filter pattern: { $.status_code >= 500 }",
            "Metric: Api5xxCount, namespace SocialOps/dev, value 1 per matching line, unit Count",
            "Health checks and non-request lines never match; no data point when no errors",
            "Defined in Terraform: infra/modules/observability/metric.tf"])
placeholder(sl,"metric filter definition (console or aws logs describe-metric-filters)",y=4.6,h=2.3)

# 5 dashboard
sl = slide("Dashboard: socialops-dev")
bullets(sl,["API 5xx (alarm annotated), ALB RequestCount / target 5xx / ELB 5xx, API response time",
            "ECS CPU and memory for api, web, worker; RDS CPU"],size=18,y=1.4)
placeholder(sl,"CloudWatch dashboard socialops-dev with error counts and resource usage",y=2.8,h=4.1)

# 6 alarm
sl = slide("Alarm and notification")
bullets(sl,["socialops-dev-api-5xx: Sum of Api5xxCount ≥ 1 in 60 s, 1 period, missing data = notBreaching",
            "ALARM and OK both publish to SNS socialops-dev-alerts → team email",
            "Controlled 5xx at 23:52:15 UTC → Api5xxCount = 1 → ALARM email about a minute later (17:53 local). Another burst: ALARM 00:10:04 → OK 00:16:04, email each time."],size=18,y=1.4)
placeholder(sl,"alarm policy page",x=0.6,y=3.2,w=5.9,h=3.7); placeholder(sl,"received alert email",x=6.8,y=3.2,w=5.9,h=3.7)

# 7 terraform
sl = slide("Terraform coverage and exceptions")
bullets(sl,["Managed (workspace dev, S3 remote state + lock): network, security groups, ALB + ACM, ECS cluster and services, RDS, Redis, S3, SQS, IAM, ECR, logs, metric filter, alarm, SNS, dashboard",
            "Not managed, with reasons: state bucket + lock table (bootstrap), Route 53 zone, SocialOps-Budget, Bedrock model access, SNS email confirmation click, us-east-2 Milestone 5 leftovers",
            "Services ignore_changes = [task_definition]: pipeline deploys are not drift",
            "Live plan, refresh on: [TODO: No changes, add screenshot]"],size=18)

# 8 cicd
sl = slide("CI/CD flow", "Every push to main; workflow .github/workflows/ci.yml; logic in scripts/ci/deploy.sh")
steps=["Lint + test","Build + push\nimages (SHA)","Assume deploy role\n(OIDC, main only)","Record running\nrevisions","Migrate\n(one-off task)","Update services,\nwait stable","Health check\nHTTPS + revision"]
for i,s in enumerate(steps): box(sl,0.4+i*1.82,2.6,1.65,1.3,s,size=12)
for i in range(6): arrow(sl,2.05+i*1.82,3.25,2.22+i*1.82,3.25)
bullets(sl,["No access keys: short-lived OIDC credentials","Deploy role: ECS update/run, PassRole to task roles only, ECR read"],y=4.6,size=18)

# 9 rollback
sl = slide("Health check and automatic rollback")
bullets(sl,["Health failed → restore recorded revisions → wait stable → re-check health → write ROLLED BACK → run fails (red)",
            "ECS circuit breaker: tasks that never start. Our step: a deployment that starts but is unhealthy",
            "Good run: [TODO run URL, SHA]    Failed + rolled back: [TODO run URL, SHA]"],size=18,y=1.4)
placeholder(sl,"pipeline: failed deploy → rollback → verified (job summary)",y=3.5,h=3.4)

# 10 controls
sl = slide("Security and cost controls kept in place")
bullets(sl,["RDS not publicly accessible (verified: PubliclyAccessible = False)","S3 access through IAM roles, not keys","Secrets in AWS Secrets Manager","No state files, keys or secrets in git [TODO: final git scan]",
            "SocialOps-Budget alert still present (verified)","Controlled failures only; no persistent data deleted"])

# 11 links
sl = slide("Links and evidence")
bullets(sl,["Live: https://app.socialops.website   https://api.socialops.website/health/ready",
            "Repo: https://github.com/Junebhone/SocialOps   branch main, SHA [TODO]",
            "Terraform: infra/    Workflow: .github/workflows/ci.yml    Metric: infra/modules/observability/metric.tf",
            "Evidence pack: docs/milestone6/ARTIFACTS.md"],size=18)

prs.save(str(Path(__file__).with_name("Milestone6_SocialOps.pptx")))
print("slides:", len(prs.slides))

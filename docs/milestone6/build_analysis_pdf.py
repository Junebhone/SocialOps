# ruff: noqa
"""Render Milestone6_Analysis.md to a one-page PDF (reportlab). Fails if it needs 2 pages."""
import re, sys
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

here = Path(__file__).parent
text = (here / "Milestone6_Analysis.md").read_text().strip().split("\n\n")

def inline(s):
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return re.sub(r"`(.+?)`", r'<font face="Courier" size="9">\1</font>', s)

h = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=12, leading=15, spaceAfter=5)
b = ParagraphStyle("b", fontName="Helvetica", fontSize=9.8, leading=13, spaceAfter=7)
out = here / "Milestone6_Analysis.pdf"
doc = SimpleDocTemplate(str(out), pagesize=letter, leftMargin=44, rightMargin=44, topMargin=38, bottomMargin=34)
flow = []
for blk in text:
    if blk.startswith("# "):
        flow.append(Paragraph(inline(blk[2:]), h))
    else:
        flow.append(Paragraph(inline(blk), b))
doc.build(flow)
n = len(re.findall(rb"/Type\s*/Page[^s]", out.read_bytes()))
print("pages:", n)
sys.exit(0 if n == 1 else 1)

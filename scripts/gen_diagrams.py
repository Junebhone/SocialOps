#!/usr/bin/env python3
"""Regenerate the pipeline diagrams in docs/architecture-phase1.md.

The two pipeline diagrams are rendered from the `pydantic-graph` definitions in
`worker/orchestrator.py`, not drawn by hand. That is one of the three things D12
bought with the graph, and it only stays true if regenerating is a command
rather than a habit: a hand-drawn diagram is wrong the first time someone adds a
node and nobody notices for a month.

The graph lives in the worker image, so the render runs there; this script only
splices the result between the markers in the document.

    make diagrams
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

DOC = Path(__file__).resolve().parent.parent / "docs" / "architecture-phase1.md"

# (marker name, expression evaluated inside the worker container)
DIAGRAMS = [
    ("comment-graph", "mermaid()"),
    ("asset-graph", "mermaid_asset()"),
]


def render(expression: str) -> str:
    result = subprocess.run(
        [
            "docker", "compose", "exec", "-T", "worker",
            "python", "-c",
            f"from worker.orchestrator import mermaid, mermaid_asset; print({expression})",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        sys.exit(f"Could not render {expression}: {result.stderr.strip()[:400]}")
    return result.stdout.strip()


def splice(document: str, name: str, body: str) -> str:
    """Replace what is between this diagram's markers, and nothing else."""
    begin = f"<!-- BEGIN GENERATED: {name} -->"
    end = f"<!-- END GENERATED: {name} -->"
    pattern = re.compile(
        rf"{re.escape(begin)}.*?{re.escape(end)}",
        re.DOTALL,
    )
    if not pattern.search(document):
        sys.exit(f"No markers for {name!r} in {DOC}")
    return pattern.sub(f"{begin}\n\n```mermaid\n{body}\n```\n\n{end}", document)


def main() -> None:
    document = DOC.read_text()
    for name, expression in DIAGRAMS:
        document = splice(document, name, render(expression))
    DOC.write_text(document)
    print(f"Regenerated {len(DIAGRAMS)} diagrams in {DOC.relative_to(Path.cwd())}")


if __name__ == "__main__":
    main()

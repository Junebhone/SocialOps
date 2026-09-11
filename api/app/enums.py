"""Every constrained string value in the schema, written exactly once.

Both sides import from here: the models render these into database CHECK
constraints, and the Pydantic schemas validate request bodies against the same
aliases. That is the point — an allowed value cannot drift between the API
boundary and the table.

Deliberately NOT a PostgreSQL native ENUM. Adding a value to a native enum is a
migration with a lock; a CHECK constraint is a migration without one, and the
values here are contract values from CLAUDE.md that a later phase may extend.
"""

from typing import Annotated, Literal, get_args

from pydantic import Field

Platform = Literal["x", "instagram", "linkedin"]

# The triage contract (CLAUDE.md, agents section).
CommentCategory = Literal["question", "complaint", "praise", "spam", "other"]
Urgency = Literal["low", "med", "high"]

# Where a comment is in the pipeline. Not an agent output — the orchestrator sets it.
CommentStatus = Literal["new", "triaged", "drafted", "replied", "failed"]

# D3: there is no "edited" status. A non-null final_text is what records an edit.
DraftStatus = Literal["pending", "approved", "rejected", "published"]

# Content drafts never reach "published": the outbox drains reply drafts only.
ContentDraftStatus = Literal["pending", "approved", "rejected"]

# Ideas never reach "published" either — approving one is inspiration only, not
# a pipeline trigger; the manager uploads a photo through the existing Content
# page same as always.
ContentIdeaStatus = Literal["proposed", "approved", "rejected"]

AgentName = Literal["triage", "response", "content", "media", "ideation", "insight"]
AgentRunStatus = Literal["ok", "error"]

# D7: entity_type is deliberately NOT constrained at the database. This alias is
# for Pydantic and for readers; a CHECK here would reintroduce the migration-per-
# new-input-type that D7 exists to avoid. "brand": the ideation agent runs per
# brand against seeded trend signals, not against one comment or asset row.
EntityType = Literal["comment", "asset", "brand"]

# D8: a 5-point ordinal, not a float. Small models do not produce calibrated
# continuous scores, and five buckets are what a human can hand-label for eval.
Sentiment = Annotated[int, Field(ge=-2, le=2)]


def sql_in(column: str, allowed: object) -> str:
    """Render a CHECK body from a Literal alias, so the DB cannot drift from Pydantic."""
    values = ", ".join(f"'{value}'" for value in get_args(allowed))
    return f"{column} IN ({values})"


def sql_in_or_null(column: str, allowed: object) -> str:
    """As `sql_in`, for a nullable column: NULL is a legal value, anything unlisted is not."""
    return f"{column} IS NULL OR {sql_in(column, allowed)}"

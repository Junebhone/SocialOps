"""Model package.

Importing this module is what registers every table on `Base.metadata`, which is
what `alembic/env.py` diffs against. A model missing from these re-exports makes
autogenerate compare a half-empty MetaData against a populated database and emit
a DROP TABLE for the tables it cannot see.
"""

from app.models.asset import Asset, ContentDraft
from app.models.base import Base
from app.models.brand import Brand, PlatformAccount
from app.models.draft import Outbox, ReplyDraft
from app.models.idea import ContentIdea
from app.models.insight import Insight
from app.models.ops import AgentRun, FailedJob
from app.models.post import Comment, Post

__all__ = [
    "AgentRun",
    "Asset",
    "Base",
    "Brand",
    "Comment",
    "ContentDraft",
    "ContentIdea",
    "FailedJob",
    "Insight",
    "Outbox",
    "PlatformAccount",
    "Post",
    "ReplyDraft",
]

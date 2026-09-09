"""The Inbox: comments with their drafts, filtered by brand."""

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.db import SessionDep
from app.enums import CommentCategory, CommentStatus
from app.models import Comment, PlatformAccount, Post, ReplyDraft
from app.routers.params import BrandIdQuery, LimitQuery, OffsetQuery
from app.schemas.comment import CommentWithDraft

router = APIRouter(prefix="/comments", tags=["comments"])

# Optional Inbox filters. Declared as aliases so the call to Query() is not
# evaluated in a default argument, matching app/routers/params.py.
CategoryFilter = Annotated[CommentCategory | None, Query(description="Filter by triage category")]
StatusFilter = Annotated[CommentStatus | None, Query(description="Filter by pipeline status")]


@router.get("", response_model=list[CommentWithDraft])
async def list_comments(
    session: SessionDep,
    brand_id: BrandIdQuery,
    category: CategoryFilter = None,
    status: StatusFilter = None,
    limit: LimitQuery = 50,
    offset: OffsetQuery = 0,
) -> Any:
    """Comments for one brand, newest first, each with its draft if it has one.

    Scoped through post -> platform_account -> brand (D17). `brand_id` is
    required: an unscoped query quietly returning another brand's comments would
    be the demo's worst moment.
    """
    draft = aliased(ReplyDraft)
    stmt = (
        select(Comment, draft)
        .join(Post, Comment.post_id == Post.id)
        .join(PlatformAccount, Post.account_id == PlatformAccount.id)
        .outerjoin(draft, draft.comment_id == Comment.id)
        .where(PlatformAccount.brand_id == brand_id)
        .order_by(Comment.created_at.desc(), Comment.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if category is not None:
        stmt = stmt.where(Comment.category == category)
    if status is not None:
        stmt = stmt.where(Comment.status == status)

    rows = (await session.execute(stmt)).all()
    return [
        CommentWithDraft.model_validate(
            {
                **{c.name: getattr(comment, c.name) for c in Comment.__table__.columns},
                "draft": draft_row,
            }
        )
        for comment, draft_row in rows
    ]


@router.get("/{comment_id}", response_model=CommentWithDraft)
async def get_comment(comment_id: int, session: SessionDep) -> Any:
    comment = await session.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")

    draft = (
        await session.execute(select(ReplyDraft).where(ReplyDraft.comment_id == comment_id))
    ).scalar_one_or_none()
    return CommentWithDraft.model_validate(
        {
            **{c.name: getattr(comment, c.name) for c in Comment.__table__.columns},
            "draft": draft,
        }
    )

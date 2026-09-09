"""Post CRUD.

`brand_id` is two hops away (post -> platform_account -> brand), so the list
endpoint joins rather than reading a denormalized column. Only `agent_runs`
carries a denormalized brand_id, and only because its dashboard query would
otherwise need a four-table join (D7).
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.db import SessionDep
from app.models import PlatformAccount, Post
from app.routers.params import BrandIdQuery, LimitQuery, OffsetQuery
from app.schemas.post import PostCreate, PostRead

router = APIRouter(prefix="/posts", tags=["posts"])


@router.get("", response_model=list[PostRead])
async def list_posts(
    session: SessionDep,
    brand_id: BrandIdQuery,
    limit: LimitQuery = 50,
    offset: OffsetQuery = 0,
) -> Any:
    stmt = (
        select(Post)
        .join(PlatformAccount, Post.account_id == PlatformAccount.id)
        .where(PlatformAccount.brand_id == brand_id)
        .order_by(Post.id)
        .limit(limit)
        .offset(offset)
    )
    return list((await session.execute(stmt)).scalars().all())


@router.get("/{post_id}", response_model=PostRead)
async def get_post(post_id: int, session: SessionDep) -> Any:
    post = await session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.post("", response_model=PostRead, status_code=201)
async def create_post(payload: PostCreate, session: SessionDep) -> Any:
    if await session.get(PlatformAccount, payload.account_id) is None:
        raise HTTPException(status_code=404, detail="Platform account not found")

    post = Post(**payload.model_dump())
    session.add(post)
    await session.commit()
    await session.refresh(post)
    return post

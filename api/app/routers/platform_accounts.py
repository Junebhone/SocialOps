"""Platform account CRUD, scoped by the required brand_id (D17)."""

from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.db import SessionDep
from app.models import Brand, PlatformAccount
from app.routers.params import BrandIdQuery, LimitQuery, OffsetQuery
from app.schemas.post import PlatformAccountCreate, PlatformAccountRead

router = APIRouter(prefix="/platform_accounts", tags=["platform_accounts"])


@router.get("", response_model=list[PlatformAccountRead])
async def list_platform_accounts(
    session: SessionDep,
    brand_id: BrandIdQuery,
    limit: LimitQuery = 50,
    offset: OffsetQuery = 0,
) -> Any:
    stmt = (
        select(PlatformAccount)
        .where(PlatformAccount.brand_id == brand_id)
        .order_by(PlatformAccount.id)
        .limit(limit)
        .offset(offset)
    )
    return list((await session.execute(stmt)).scalars().all())


@router.get("/{account_id}", response_model=PlatformAccountRead)
async def get_platform_account(account_id: int, session: SessionDep) -> Any:
    account = await session.get(PlatformAccount, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Platform account not found")
    return account


@router.post("", response_model=PlatformAccountRead, status_code=201)
async def create_platform_account(payload: PlatformAccountCreate, session: SessionDep) -> Any:
    # A clean 404 beats an unhandled IntegrityError surfacing as a 500.
    if await session.get(Brand, payload.brand_id) is None:
        raise HTTPException(status_code=404, detail="Brand not found")

    account = PlatformAccount(**payload.model_dump())
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account

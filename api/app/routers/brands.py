"""Brand CRUD.

The one documented exception to D17: `GET /brands` takes no `brand_id`, because
it is the endpoint the brand selector itself calls to populate its options.
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.db import SessionDep
from app.models import Brand
from app.routers.params import LimitQuery, OffsetQuery
from app.schemas.brand import BrandCreate, BrandRead

router = APIRouter(prefix="/brands", tags=["brands"])


@router.get("", response_model=list[BrandRead])
async def list_brands(
    session: SessionDep,
    limit: LimitQuery = 50,
    offset: OffsetQuery = 0,
) -> Any:
    stmt = select(Brand).order_by(Brand.id).limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().all())


@router.get("/{brand_id}", response_model=BrandRead)
async def get_brand(brand_id: int, session: SessionDep) -> Any:
    brand = await session.get(Brand, brand_id)
    if brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand


@router.post("", response_model=BrandRead, status_code=201)
async def create_brand(payload: BrandCreate, session: SessionDep) -> Any:
    brand = Brand(
        name=payload.name,
        voice_guidelines=payload.voice_guidelines,
        # The column is JSONB; the typed model is the boundary contract (D16).
        brand_rules_json=payload.brand_rules_json.model_dump(),
    )
    session.add(brand)
    # Commit in the route, never in the session dependency.
    await session.commit()
    await session.refresh(brand)
    return brand

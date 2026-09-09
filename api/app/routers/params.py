"""Query parameters shared by every list endpoint."""

from typing import Annotated

from fastapi import Query

# D17. No default — that alone is what makes it required, so an omitted brand_id
# is a 422 rather than an unscoped query quietly returning another brand's rows.
BrandIdQuery = Annotated[
    int,
    Query(description="Brand scope. Required: a shared link must resolve to the same view."),
]

LimitQuery = Annotated[int, Query(ge=1, le=200)]
OffsetQuery = Annotated[int, Query(ge=0)]

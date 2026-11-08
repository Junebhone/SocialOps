"""A controlled 5xx, for proving the error metric and alarm (Milestone 6).

Off by default: unless ENABLE_ERROR_ROUTE is true, the route answers 404 as if it
did not exist, so the public cannot trigger alerts on a deployment that has not
opted in. Two modes cover both ways a real request fails:

- `kind=status` (default): the handler returns a 500 response. Logged by the
  normal `request` line with status_code 500.
- `kind=raise`: the handler raises an unhandled exception. Logged by the
  `request.failed` line, which now carries status_code 500 too.

Either way, one request produces exactly one log line with status_code >= 500,
which is what the CloudWatch metric filter counts.
"""

from typing import Literal

from fastapi import APIRouter, HTTPException

from app.config import get_settings

router = APIRouter(prefix="/debug", tags=["debug"])


class ControlledError(RuntimeError):
    """Raised on purpose by GET /debug/error?kind=raise."""


@router.get("/error", include_in_schema=False)
async def controlled_error(kind: Literal["status", "raise"] = "status") -> None:
    if not get_settings().enable_error_route:
        raise HTTPException(status_code=404, detail="Not Found")
    if kind == "raise":
        raise ControlledError("controlled failure for the 5xx metric demo")
    raise HTTPException(status_code=500, detail="controlled error for the 5xx metric demo")

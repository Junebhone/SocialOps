"""A controlled 5xx, for proving the error metric and alarm (Milestone 6).

Off by default: unless ENABLE_ERROR_ROUTE is true, or the SSM parameter named by
ERROR_ROUTE_SSM_PARAMETER holds "true", the route answers 404 as if it did not exist, so the public cannot trigger alerts on a deployment that has not
opted in. Two modes cover both ways a real request fails:

- `kind=status` (default): the handler returns a 500 response. Logged by the
  normal `request` line with status_code 500.
- `kind=raise`: the handler raises an unhandled exception. Logged by the
  `request.failed` line, which now carries status_code 500 too.

Either way, one request produces exactly one log line with status_code >= 500,
which is what the CloudWatch metric filter counts.
"""

import asyncio
from typing import Literal

import boto3
from fastapi import APIRouter, HTTPException

from app.config import get_settings

router = APIRouter(prefix="/debug", tags=["debug"])


class ControlledError(RuntimeError):
    """Raised on purpose by GET /debug/error?kind=raise."""


def _read_ssm_flag(name: str, region: str | None) -> bool:
    """True only if the parameter exists and holds "true". Any error is off: the
    route must never open because the lookup failed."""
    try:
        client = boto3.client("ssm", region_name=region)
        value = client.get_parameter(Name=name)["Parameter"]["Value"]
    except Exception:
        return False
    return value.strip().lower() == "true"


async def _route_enabled() -> bool:
    """Read on every call, never cached (hard rule #2: the API holds no state), so
    flipping the parameter takes effect on the next request. Only this demo route
    pays for the lookup."""
    settings = get_settings()
    if settings.enable_error_route:
        return True
    if settings.error_route_ssm_parameter:
        return await asyncio.to_thread(
            _read_ssm_flag, settings.error_route_ssm_parameter, settings.aws_region
        )
    return False


@router.get("/error", include_in_schema=False)
async def controlled_error(kind: Literal["status", "raise"] = "status") -> None:
    if not await _route_enabled():
        raise HTTPException(status_code=404, detail="Not Found")
    if kind == "raise":
        raise ControlledError("controlled failure for the 5xx metric demo")
    raise HTTPException(status_code=500, detail="controlled error for the 5xx metric demo")

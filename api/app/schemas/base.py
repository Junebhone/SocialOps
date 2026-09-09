"""Base classes for request and response schemas."""

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """Base for every *Read* schema.

    `from_attributes` does not propagate into nested models, only to subclasses,
    so every Read schema inherits from here rather than setting it ad hoc.
    """

    model_config = ConfigDict(from_attributes=True)


class CreateModel(BaseModel):
    """Base for every request body.

    `extra="forbid"` stops a client POSTing fields it does not own — an `id`, or
    a `status` that only the orchestrator may set.
    """

    model_config = ConfigDict(extra="forbid")

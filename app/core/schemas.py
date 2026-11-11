from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base schema: snake_case in Python, camelCase in JSON (what the React frontend expects)."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class CamelInputModel(CamelModel):
    """Base for request bodies: unknown fields are rejected with 422 instead of silently dropped.

    A typo such as "lastUsedyear" in the frontend would otherwise lose data without any error.
    """

    model_config = ConfigDict(extra="forbid")

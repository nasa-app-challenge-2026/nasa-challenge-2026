"""Base of the wire models: snake_case in Python, camelCase on the wire (the contract format)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """A model that is read and written in camelCase. Unknown fields are ignored: the front end
    sends its whole farm (outline, names…) and the algorithm only reads what it needs."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")

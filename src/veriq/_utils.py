from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic import BaseModel


def model_to_flat_dict(model_instance: BaseModel) -> dict[str, Any]:
    """Convert model to dict without recursive conversion."""
    model = model_instance.__class__
    result = {}
    for field_name in model.model_fields:
        result[field_name] = getattr(model_instance, field_name)
    return result

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from ._path import AttributePart, ItemPart, PartBase
from ._table import Table

if TYPE_CHECKING:
    from collections.abc import Generator


def model_to_flat_dict(model: type[BaseModel]) -> dict[str, Any]:
    """Convert model to dict without recursive conversion."""
    result = {}
    for field_name in model.model_fields:
        result[field_name] = getattr(model_instance, field_name)
    return result


def iter_leaf_path_parts(
    model: Any,
    *,
    _current_path_parts: tuple[PartBase, ...] = (),
) -> Generator[tuple[PartBase, ...]]:
    if not issubclass(model, BaseModel):
        yield _current_path_parts

    for field_name, field_info in model.model_fields.items():
        field_type = field_info.annotation

        if field_type is None:
            continue
        elif issubclass(field_type, BaseModel):
            yield from iter_leaf_path_parts(
                field_type,
                _current_path_parts=(*_current_path_parts, AttributePart(name=field_name)),
            )
        elif issubclass(field_type, Table):
            for key in field_type.expected_keys:
                yield (
                    *_current_path_parts,
                    AttributePart(name=field_name),
                    ItemPart(key=key),
                )
        else:
            yield (*_current_path_parts, AttributePart(name=field_name))

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import tomli_w

from ._path import AttributePart, CalcPath, ItemPart, ModelPath, PartBase, ProjectPath, VerificationPath
from ._table import Table

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pydantic import BaseModel

    from ._models import Project

logger = logging.getLogger(__name__)


def _serialize_value(value: Any) -> Any:
    """Serialize a value for TOML export, handling special types like Table."""
    if isinstance(value, Table):
        # Convert Table (dict with enum keys) to dict with string keys
        return {k.value if hasattr(k, "value") else str(k): v for k, v in value.items()}
    return value


def _set_nested_value(data: dict[str, Any], keys: list[str], value: Any) -> None:
    """Set a value in a nested dictionary using a list of keys."""
    current = data
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    current[keys[-1]] = _serialize_value(value)


def _parts_to_keys(parts: tuple[PartBase, ...]) -> list[str]:
    """Convert path parts to a list of keys for nested dictionary access."""
    keys: list[str] = []
    for part in parts:
        match part:
            case AttributePart(name):
                keys.append(name)
            case ItemPart(key):
                # For Table items, use the key directly as a dictionary key
                if isinstance(key, tuple):
                    # Multi-key access (though not common in this context)
                    keys.append(",".join(key))
                else:
                    keys.append(key)
            case _:
                msg = f"Unknown part type: {type(part)}"
                raise TypeError(msg)
    return keys


def export_to_toml(
    _project: Project,
    _model_data: Mapping[str, BaseModel],
    results: dict[ProjectPath, Any],
    output_path: Path | str,
) -> None:
    """Export model data and evaluation results to a TOML file.

    Args:
        project: The project containing scope definitions
        model_data: The input model data for each scope
        results: The evaluation results from evaluate_project
        output_path: Path to the output TOML file

    """
    toml_data: dict[str, Any] = {}

    # Process all results (includes both model data and calculated/verified values)
    for ppath, value in results.items():
        scope_name = ppath.scope
        path = ppath.path

        # Build the section name based on the path type
        if isinstance(path, ModelPath):
            # Model paths: {scope}.model.{field_path}
            section_keys = [scope_name, "model"]
            field_keys = _parts_to_keys(path.parts)
        elif isinstance(path, CalcPath):
            # Calculation paths: {scope}.calc.{calc_name}.{field_path}
            section_keys = [scope_name, "calc", path.calc_name]
            field_keys = _parts_to_keys(path.parts)
        elif isinstance(path, VerificationPath):
            # Verification paths: {scope}.verification.{verification_name}
            section_keys = [scope_name, "verification"]
            field_keys = [path.verification_name]
        else:
            msg = f"Unknown path type: {type(path)}"
            raise TypeError(msg)

        # Combine section and field keys
        all_keys = section_keys + field_keys

        # Set the value in the nested dictionary
        _set_nested_value(toml_data, all_keys, value)

    # Write to TOML file
    output_path = Path(output_path)
    with output_path.open("wb") as f:
        tomli_w.dump(toml_data, f)

    logger.info(f"Exported results to {output_path}")

"""Utilities to discover veriq projects and modules.

This module was adapted from `fastapi_cli.discover` of package `fastapi-cli` version 0.0.8 (77e6d1f).
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class ModuleData:
    """Module data for a Python module."""

    module_import_str: str
    extra_sys_path: Path
    module_paths: list[Path]


def get_module_data_from_path(path: Path) -> ModuleData:
    """Get module data from a file path.

    Args:
        path: Path to a Python file or package

    Returns:
        ModuleData containing module import information

    """
    use_path = path.resolve()
    module_path = use_path
    if use_path.is_file() and use_path.stem == "__init__":
        module_path = use_path.parent
    module_paths = [module_path]
    extra_sys_path = module_path.parent
    for parent in module_path.parents:
        init_path = parent / "__init__.py"
        if init_path.is_file():
            module_paths.insert(0, parent)
            extra_sys_path = parent.parent
        else:
            break

    module_str = ".".join(p.stem for p in module_paths)
    return ModuleData(
        module_import_str=module_str,
        extra_sys_path=extra_sys_path.resolve(),
        module_paths=module_paths,
    )

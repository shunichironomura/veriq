"""Utilities to discover veriq scope.

This module was adapted from `fastapi_cli.discover` of package `fastapi-cli` version 0.0.8 (77e6d1f).
"""

import importlib
import sys
from dataclasses import dataclass
from logging import getLogger
from typing import TYPE_CHECKING

from veriq._exceptions import VeriqCLIEError
from veriq._models import Scope

if TYPE_CHECKING:
    from pathlib import Path

logger = getLogger(__name__)


@dataclass
class ModuleData:
    module_import_str: str
    extra_sys_path: Path
    module_paths: list[Path]


def get_module_data_from_path(path: Path) -> ModuleData:
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


def get_scope_name(*, mod_data: ModuleData, scope_name: str | None = None) -> str:
    try:
        mod = importlib.import_module(mod_data.module_import_str)
    except (ImportError, ValueError):
        logger.exception("Import error")
        logger.warning("Ensure all the package directories have an [blue]__init__.py[/blue] file")
        raise

    object_names = dir(mod)
    object_names_set = set(object_names)
    if scope_name:
        if scope_name not in object_names_set:
            msg = f"Could not find a scope name {scope_name} in {mod_data.module_import_str}"
            raise VeriqCLIEError(msg)
        scope = getattr(mod, scope_name)
        if not isinstance(scope, Scope):
            msg = f"The scope name {scope_name} in {mod_data.module_import_str} doesn't seem to be a Veriq scope"
            raise VeriqCLIEError(msg)
        return scope_name
    for name in object_names:
        obj = getattr(mod, name)
        if isinstance(obj, Scope):
            return name
    msg = "Could not find Veriq scope in module, try using --scope"
    raise VeriqCLIEError(msg)


@dataclass
class ImportData:
    scope_name: str
    module_data: ModuleData
    import_string: str


def get_import_data(
    *,
    path: Path,
    scope_name: str | None = None,
) -> ImportData:
    logger.debug(f"Using path [blue]{path}[/blue]")
    logger.debug(f"Resolved absolute path {path.resolve()}")

    if not path.exists():
        msg = f"Path does not exist {path}"
        raise VeriqCLIEError(msg)
    mod_data = get_module_data_from_path(path)
    sys.path.insert(0, str(mod_data.extra_sys_path))
    use_scope_name = get_scope_name(mod_data=mod_data, scope_name=scope_name)

    import_string = f"{mod_data.module_import_str}:{use_scope_name}"

    return ImportData(
        scope_name=use_scope_name,
        module_data=mod_data,
        import_string=import_string,
    )

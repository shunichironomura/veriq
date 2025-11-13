import importlib
import json
import logging
import sys
import tomllib
from typing import TYPE_CHECKING, Annotated, NoReturn

import typer

from veriq._models import Scope

from .discover import get_import_data

if TYPE_CHECKING:
    from pathlib import Path
app = typer.Typer()

logger = logging.getLogger(__name__)


@app.callback()
def callback(
    *,
    verbose: bool = typer.Option(default=False, help="Enable verbose output"),
) -> None:
    """Veriq CLI."""
    log_level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(level=log_level)


@app.command()
def schema(
    path: Annotated[
        Path,
        typer.Argument(help="Path to the Python file containing a Veriq scope."),
    ],
    *,
    scope_name: Annotated[
        str | None,
        typer.Option(help="Name of the Veriq scope in the Python file. If not provided, the scope will be inferred."),
    ] = None,
    include_child_scopes: Annotated[
        bool,
        typer.Option(help="Include child scopes in the generated schema."),
    ] = False,
    leaf_only: Annotated[
        bool,
        typer.Option(help="Include only leaf scopes in the generated schema."),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option(help="Path to the output file for the generated schema."),
    ] = None,
) -> NoReturn:
    logger.info("Generating schema...")
    import_data = get_import_data(path=path, scope_name=scope_name)
    logger.debug(f"Importing from {import_data.module_data.extra_sys_path}")
    logger.debug(f"Importing module {import_data.module_data.module_import_str}")
    logger.debug(f"Import string: {import_data.import_string}")
    logger.debug(f"Sys path: {sys.path}")

    scope = _load_scope(import_data.module_data.module_import_str, import_data.scope_name)
    logger.debug(f"Loaded scope: {scope}")

    json_schema = scope.design_json_schema(include_child_scopes=include_child_scopes, leaf_only=leaf_only)

    if output is None:
        output = path.parent / (path.name + ".schema.json")

    logger.info(f"Writing schema to {output}")

    with output.open("w") as f:
        json.dump(json_schema, f, indent=2)

    raise typer.Exit(0)


@app.command()
def verify(
    path: Annotated[
        Path,
        typer.Argument(help="Path to the Python file containing a Veriq scope."),
    ],
    *,
    design: Annotated[
        Path | None,
        typer.Option(
            help="Path to the design file (TOML format) to be verified. If not provided, the design will be inferred.",
        ),
    ] = None,
    scope_name: Annotated[
        str | None,
        typer.Option(help="Name of the Veriq scope in the Python file. If not provided, the scope will be inferred."),
    ] = None,
    include_child_scopes: Annotated[
        bool,
        typer.Option(help="Include child scopes in the generated schema."),
    ] = False,
    leaf_only: Annotated[
        bool,
        typer.Option(help="Include only leaf scopes in the generated schema."),
    ] = False,
) -> NoReturn:
    logger.info("Generating schema...")
    import_data = get_import_data(path=path, scope_name=scope_name)
    logger.debug(f"Importing from {import_data.module_data.extra_sys_path}")
    logger.debug(f"Importing module {import_data.module_data.module_import_str}")
    logger.debug(f"Import string: {import_data.import_string}")
    logger.debug(f"Sys path: {sys.path}")

    scope = _load_scope(import_data.module_data.module_import_str, import_data.scope_name)
    logger.debug(f"Loaded scope: {scope}")

    if design is None:
        design = path.parent / (path.name + ".design.toml")
    logger.info(f"Using design file {design}")

    DesignModel = scope.design_model(include_child_scopes=include_child_scopes, leaf_only=leaf_only)  # noqa: N806
    with design.open("rb") as f:
        design_data = DesignModel.model_validate(tomllib.load(f))

    verification_result = scope.verify_design(
        design_data,
        include_child_scopes=include_child_scopes,
        leaf_only=leaf_only,
    )
    if verification_result:
        logger.info("Design verification succeeded.")
        raise typer.Exit(0)
    logger.error("Design verification failed.")
    raise typer.Exit(1)


def _load_scope(module_name: str, scope_name: str) -> Scope:
    """Load a Veriq scope from a module."""
    module = importlib.import_module(module_name)
    attr = getattr(module, scope_name)
    if not isinstance(attr, Scope):
        msg = f"{scope_name} is not a Veriq Scope"
        raise TypeError(msg)
    return attr


def main() -> None:
    app()

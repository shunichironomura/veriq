import importlib
import logging
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from veriq._build import build_dependencies_graph
from veriq._eval import evaluate_project
from veriq._io import export_to_toml, load_model_data_from_toml
from veriq._models import Project
from veriq._path import VerificationPath

from .discover import get_module_data_from_path

app = typer.Typer()

logger = logging.getLogger(__name__)
console = Console()


@app.callback()
def callback(
    *,
    verbose: bool = typer.Option(default=False, help="Enable verbose output"),
) -> None:
    """Veriq CLI."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level)


def _load_project_from_script(script_path: Path, project_name: str | None = None) -> Project:
    """Load a project from a Python script path.

    Args:
        script_path: Path to the Python script containing the project
        project_name: Name of the project variable. If None, infers from the script

    Returns:
        The loaded Project instance

    """
    module_data = get_module_data_from_path(script_path)
    sys.path.insert(0, str(module_data.extra_sys_path))

    try:
        module = importlib.import_module(module_data.module_import_str)
    except (ImportError, ValueError):
        logger.exception("Import error")
        logger.warning("Ensure all the package directories have an __init__.py file")
        raise

    if project_name:
        if not hasattr(module, project_name):
            msg = f"Could not find project '{project_name}' in {module_data.module_import_str}"
            raise ValueError(msg)
        project = getattr(module, project_name)
        if not isinstance(project, Project):
            msg = f"'{project_name}' in {module_data.module_import_str} is not a Project instance"
            raise TypeError(msg)
        return project

    # Infer project from module
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, Project):
            logger.info(f"Found project: {name}")
            return obj

    msg = "Could not find Project in module, try using --project"
    raise ValueError(msg)


def _load_project_from_module_path(module_path: str) -> Project:
    """Load a project from a module path (e.g., 'examples.dummysat:project').

    Args:
        module_path: Module path in format 'module.path:variable_name'

    Returns:
        The loaded Project instance

    """
    if ":" not in module_path:
        msg = "Module path must be in format 'module.path:variable_name'"
        raise ValueError(msg)

    module_name, project_name = module_path.split(":", 1)
    module = importlib.import_module(module_name)
    project = getattr(module, project_name)

    if not isinstance(project, Project):
        msg = f"'{project_name}' in module '{module_name}' is not a Project instance"
        raise TypeError(msg)

    return project


@app.command()
def calc(
    path: Annotated[
        str,
        typer.Argument(help="Path to Python script or module path (e.g., examples.dummysat:project)"),
    ],
    *,
    input: Annotated[  # noqa: A002
        Path,
        typer.Option("-i", "--input", help="Path to input TOML file"),
    ],
    output: Annotated[
        Path,
        typer.Option("-o", "--output", help="Path to output TOML file"),
    ],
    project_var: Annotated[
        str | None,
        typer.Option("--project", help="Name of the project variable (for script paths only)"),
    ] = None,
    verify: Annotated[
        bool,
        typer.Option("--verify", help="Verify that all verifications pass (exit non-zero if any fail)"),
    ] = False,
) -> None:
    """Perform calculations on a project and export results."""
    # Load the project
    if ":" in path:
        # Module path format
        logger.info(f"Loading project from module path: {path}")
        project = _load_project_from_module_path(path)
    else:
        # Script path format
        script_path = Path(path)
        logger.info(f"Loading project from script: {script_path}")
        project = _load_project_from_script(script_path, project_var)

    logger.info(f"Loaded project: {project.name}")

    # Load model data
    logger.info(f"Loading model data from: {input}")
    model_data = load_model_data_from_toml(project, input)

    # Evaluate the project
    logger.info("Evaluating project...")
    results = evaluate_project(project, model_data)

    # Check verifications if requested
    if verify:
        verification_failed = False
        for ppath, value in results.items():
            if isinstance(ppath.path, VerificationPath):
                verification_name = ppath.path.verification_name
                scope_name = ppath.scope
                if not value:
                    console.print(
                        f"[red]✗[/red] Verification failed: {scope_name}.{verification_name}",
                        style="red",
                    )
                    verification_failed = True
                else:
                    console.print(
                        f"[green]✓[/green] Verification passed: {scope_name}.{verification_name}",
                        style="green",
                    )

        if verification_failed:
            logger.error("Some verifications failed")
            raise typer.Exit(1)
        logger.info("All verifications passed")

    # Export results
    logger.info(f"Exporting results to: {output}")
    export_to_toml(project, model_data, results, output)

    console.print(f"[green]✓[/green] Results exported to {output}")


@app.command()
def check(
    path: Annotated[
        str,
        typer.Argument(help="Path to Python script or module path (e.g., examples.dummysat:project)"),
    ],
    *,
    project_var: Annotated[
        str | None,
        typer.Option("--project", help="Name of the project variable (for script paths only)"),
    ] = None,
) -> None:
    """Check the validity of a project without performing calculations."""
    # Load the project
    if ":" in path:
        # Module path format
        logger.info(f"Loading project from module path: {path}")
        project = _load_project_from_module_path(path)
    else:
        # Script path format
        script_path = Path(path)
        logger.info(f"Loading project from script: {script_path}")
        project = _load_project_from_script(script_path, project_var)

    logger.info(f"Loaded project: {project.name}")

    # Check if building the dependencies graph raises any errors
    build_dependencies_graph(project)

    # Display project information
    console.print(f"\n[bold]Project:[/bold] {project.name}")
    console.print(f"[bold]Scopes:[/bold] {len(project.scopes)}")
    for scope_name, scope in project.scopes.items():
        num_calcs = len(scope.calculations)
        num_verifs = len(scope.verifications)
        console.print(f"  • {scope_name}: {num_calcs} calculations, {num_verifs} verifications")

    console.print("\n[green]✓[/green] Project is valid")


def main() -> None:
    app()

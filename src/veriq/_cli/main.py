import importlib
import logging
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from veriq._build import build_dependencies_graph
from veriq._eval import evaluate_project
from veriq._io import export_to_toml, load_model_data_from_toml
from veriq._models import Project
from veriq._path import VerificationPath

from .discover import get_module_data_from_path

app = typer.Typer()

logger = logging.getLogger(__name__)
# Console for stderr (info/errors)
err_console = Console(stderr=True)
# Console for stdout (results)
out_console = Console()


@app.callback()
def callback(
    *,
    verbose: bool = typer.Option(default=False, help="Enable verbose output"),
) -> None:
    """Veriq CLI."""
    log_level = logging.DEBUG if verbose else logging.INFO

    # Configure rich logging handler to output to stderr
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        handlers=[
            RichHandler(
                console=err_console,
                show_time=False,
                show_path=verbose,
                rich_tracebacks=True,
            ),
        ],
    )


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
            logger.debug(f"Found project: {name}")
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
    err_console.print()

    # Load the project
    if ":" in path:
        # Module path format
        err_console.print(f"[cyan]Loading project from module:[/cyan] {path}")
        project = _load_project_from_module_path(path)
    else:
        # Script path format
        script_path = Path(path)
        err_console.print(f"[cyan]Loading project from script:[/cyan] {script_path}")
        project = _load_project_from_script(script_path, project_var)

    err_console.print(f"[cyan]Project:[/cyan] [bold]{project.name}[/bold]")
    err_console.print()

    # Load model data
    err_console.print(f"[cyan]Loading input from:[/cyan] {input}")
    model_data = load_model_data_from_toml(project, input)

    # Evaluate the project
    err_console.print("[cyan]Evaluating project...[/cyan]")
    results = evaluate_project(project, model_data)
    err_console.print()

    # Check verifications if requested
    if verify:
        verification_failed = False
        verification_results: list[tuple[str, bool]] = []

        for ppath, value in results.items():
            if isinstance(ppath.path, VerificationPath):
                verification_name = ppath.path.verification_name
                scope_name = ppath.scope
                verification_results.append((f"{scope_name}::?{verification_name}", value))
                if not value:
                    verification_failed = True

        # Create a table for verification results
        if verification_results:
            table = Table(show_header=True, header_style="bold cyan", box=None)
            table.add_column("Verification", style="dim")
            table.add_column("Result", justify="center")

            for verif_name, passed in verification_results:
                status = "[green]✓ PASS[/green]" if passed else "[red]✗ FAIL[/red]"
                table.add_row(verif_name, status)

            err_console.print(Panel(table, title="[bold]Verification Results[/bold]", border_style="cyan"))
            err_console.print()

        if verification_failed:
            err_console.print("[red]✗ Some verifications failed[/red]")
            raise typer.Exit(1)

    # Export results
    err_console.print(f"[cyan]Exporting results to:[/cyan] {output}")
    export_to_toml(project, model_data, results, output)

    err_console.print()
    err_console.print("[green]✓ Calculation complete[/green]")
    err_console.print()


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
    err_console.print()

    # Load the project
    if ":" in path:
        # Module path format
        err_console.print(f"[cyan]Loading project from module:[/cyan] {path}")
        project = _load_project_from_module_path(path)
    else:
        # Script path format
        script_path = Path(path)
        err_console.print(f"[cyan]Loading project from script:[/cyan] {script_path}")
        project = _load_project_from_script(script_path, project_var)

    err_console.print(f"[cyan]Project:[/cyan] [bold]{project.name}[/bold]")
    err_console.print()

    # Check if building the dependencies graph raises any errors
    err_console.print("[cyan]Validating dependencies...[/cyan]")
    build_dependencies_graph(project)
    err_console.print()

    # Create a table for project information
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Scope", style="bold")
    table.add_column("Calculations", justify="right", style="yellow")
    table.add_column("Verifications", justify="right", style="green")

    for scope_name, scope in project.scopes.items():
        num_calcs = len(scope.calculations)
        num_verifs = len(scope.verifications)
        table.add_row(scope_name, str(num_calcs), str(num_verifs))

    err_console.print(
        Panel(
            table,
            title=f"[bold]Project: {project.name}[/bold]",
            subtitle=f"[dim]{len(project.scopes)} scopes[/dim]",
            border_style="cyan",
        ),
    )

    err_console.print()
    err_console.print("[green]✓ Project is valid[/green]")
    err_console.print()


def main() -> None:
    app()

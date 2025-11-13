"""Requirements verification tool."""

__all__ = [
    "Project",
    "Ref",
    "Requirement",
    "Scope",
    "Table",
    "assume",
    "build_dependencies_graph",
    "depends",
]

from ._decorators import assume
from ._exec import build_dependencies_graph
from ._models import Project, Ref, Requirement, Scope
from ._relations import depends
from ._table import Table

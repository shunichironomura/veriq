"""Requirements verification tool."""

__all__ = [
    "Depends",
    "Project",
    "Requirement",
    "Scope",
    "Table",
    "assume",
    "depends",
]

from ._decorators import assume
from ._models import Depends, Project, Requirement, Scope
from ._relations import depends
from ._table import Table

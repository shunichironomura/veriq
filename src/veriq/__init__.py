"""Requirements verification tool."""

__all__ = [
    "Depends",
    "Requirement",
    "Scope",
    "Table",
    "assume",
    "depends",
]

from ._decorators import assume
from ._models import Depends, Requirement, Scope
from ._relations import depends
from ._table import Table

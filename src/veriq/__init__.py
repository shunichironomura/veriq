"""Requirements verification tool."""

__all__ = [
    "Depends",
    "Requirement",
    "Scope",
    "calculation",
    "child",
    "depends",
    "verification",
]

from ._decorators import calculation, verification
from ._models import Depends, Requirement, Scope
from ._relations import child, depends

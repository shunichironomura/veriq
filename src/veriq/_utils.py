from annotationlib import ForwardRef
from collections import defaultdict, deque
from collections.abc import Collection, Hashable, Mapping
from inspect import isclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from ._path import AttributePart, ItemPart, PartBase
from ._table import Table

if TYPE_CHECKING:
    from collections.abc import Generator


def iter_leaf_path_parts(
    model: Any,
    *,
    _current_path_parts: tuple[PartBase, ...] = (),
) -> Generator[tuple[PartBase, ...]]:
    if isinstance(model, ForwardRef):
        model = model.evaluate()

    if not isclass(model):
        yield _current_path_parts
        return
    if issubclass(model, Table):
        for key in model.expected_keys:
            yield (
                *_current_path_parts,
                ItemPart(key=key),
            )
        return
    if not issubclass(model, BaseModel):
        yield _current_path_parts
        return

    for field_name, field_info in model.model_fields.items():
        field_type = field_info.annotation
        if isinstance(field_type, ForwardRef):
            field_type = field_type.evaluate()
        if field_type is None:
            continue
        yield from iter_leaf_path_parts(
            field_type,
            _current_path_parts=(*_current_path_parts, AttributePart(name=field_name)),
        )


def topological_sort[T: Hashable](dependencies: Mapping[T, Collection[T]]) -> list[T]:
    """Sort a graph of dependencies topologically.

    Given a dependency graph (a dict mapping a node to a collection of nodes that depend on it),
    perform a topological sort and return an ordered list of nodes.
    Raises an error if a cycle is detected.
    """
    indegree: defaultdict[T, int] = defaultdict(int)
    for node, deps in dependencies.items():
        indegree[node] = indegree.get(node, 0)
        for dep in deps:
            indegree[dep] += 1
    q = deque([node for node, deg in indegree.items() if deg == 0])
    order = []
    while q:
        node = q.popleft()
        order.append(node)
        for dep in dependencies.get(node, []):
            indegree[dep] -= 1
            if indegree[dep] == 0:
                q.append(dep)
    if len(order) != len(indegree):
        msg = "Cycle detected in relationship dependencies!"
        raise ValueError(msg)
    return order

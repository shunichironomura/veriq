from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ._path import CalcPath, ModelPath, ProjectPath, VerificationPath, iter_leaf_path_parts

if TYPE_CHECKING:
    from ._models import Project


@dataclass(slots=True)
class DepencenciesGraph:
    predecessors: dict[ProjectPath, set[ProjectPath]]
    successors: dict[ProjectPath, set[ProjectPath]]


def build_dependencies_graph(project: Project) -> DepencenciesGraph:  # noqa: PLR0912, C901
    predecessors_dd: defaultdict[ProjectPath, set[ProjectPath]] = defaultdict(set)
    successors_dd: defaultdict[ProjectPath, set[ProjectPath]] = defaultdict(set)

    for scope_name, scope in project.scopes.items():
        for calc_name, calc in scope.calculations.items():
            for dep_ppath in calc.dep_ppaths.values():
                dep_type = project.get_type(dep_ppath)
                for src_leaf_parts in iter_leaf_path_parts(dep_type):
                    src_leaf_abs_parts = dep_ppath.path.parts + src_leaf_parts
                    src_leaf_path: ModelPath | CalcPath
                    if isinstance(dep_ppath.path, ModelPath):
                        src_leaf_path = ModelPath(root="$", parts=src_leaf_abs_parts)
                    elif isinstance(dep_ppath.path, CalcPath):
                        src_leaf_path = CalcPath(root=dep_ppath.path.root, parts=src_leaf_abs_parts)
                    else:
                        msg = f"Unsupported dependency path type: {type(dep_ppath.path)}"
                        raise TypeError(msg)
                    src_leaf_ppath = ProjectPath(
                        scope=dep_ppath.scope,
                        path=src_leaf_path,
                    )
                    for dst_leaf_parts in iter_leaf_path_parts(calc.output_type):
                        dst_leaf_ppath = ProjectPath(
                            scope=scope_name,
                            path=CalcPath(root=f"@{calc_name}", parts=dst_leaf_parts),
                        )
                        predecessors_dd[dst_leaf_ppath].add(src_leaf_ppath)
                        successors_dd[src_leaf_ppath].add(dst_leaf_ppath)

        for verif_name, verif in scope.verifications.items():
            for dep_ppath in verif.dep_ppaths.values():
                dep_type = project.get_type(dep_ppath)
                for src_leaf_parts in iter_leaf_path_parts(dep_type):
                    src_leaf_abs_parts = dep_ppath.path.parts + src_leaf_parts
                    if isinstance(dep_ppath.path, ModelPath):
                        src_leaf_path = ModelPath(root="$", parts=src_leaf_abs_parts)
                    elif isinstance(dep_ppath.path, CalcPath):
                        src_leaf_path = CalcPath(root=dep_ppath.path.root, parts=src_leaf_abs_parts)
                    else:
                        msg = f"Unsupported dependency path type: {type(dep_ppath.path)}"
                        raise TypeError(msg)
                    src_leaf_ppath = ProjectPath(
                        scope=dep_ppath.scope,
                        path=src_leaf_path,
                    )
                    dst_leaf_ppath = ProjectPath(
                        scope=scope_name,
                        path=VerificationPath(root=f"?{verif_name}"),
                    )
                    predecessors_dd[dst_leaf_ppath].add(src_leaf_ppath)
                    successors_dd[src_leaf_ppath].add(dst_leaf_ppath)

    return DepencenciesGraph(
        predecessors=dict(predecessors_dd),
        successors=dict(successors_dd),
    )

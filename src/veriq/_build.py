from collections import defaultdict
from typing import TYPE_CHECKING

from ._path import CalcPath, ModelPath, ProjectPath, VerificationPath
from ._utils import iter_leaf_path_parts

if TYPE_CHECKING:
    from ._models import Project


def build_dependencies_graph(project: Project) -> dict[ProjectPath, set[ProjectPath]]:  # noqa: PLR0912, C901
    dependencies_dd: defaultdict[ProjectPath, set[ProjectPath]] = defaultdict(set)

    for scope_name, scope in project.scopes.items():
        for calc_name, calc in scope.calculations.items():
            for dep_ppath in calc.dep_ppaths.values():
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
                    for dst_leaf_parts in iter_leaf_path_parts(calc.output_type):
                        dst_leaf_ppath = ProjectPath(
                            scope=scope_name,
                            path=CalcPath(root=f"@{calc_name}", parts=dst_leaf_parts),
                        )
                        dependencies_dd[src_leaf_ppath].add(dst_leaf_ppath)

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
                    dependencies_dd[src_leaf_ppath].add(dst_leaf_ppath)

    return dict(dependencies_dd)

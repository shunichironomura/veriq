from collections import defaultdict
from typing import TYPE_CHECKING

from ._path import CalcPath, ProjectPath, VerificationPath
from ._utils import iter_leaf_path_parts

if TYPE_CHECKING:
    from ._models import Project


def build_dependencies_graph(project: Project) -> dict[ProjectPath, set[ProjectPath]]:
    dependencies_dd: defaultdict[ProjectPath, set[ProjectPath]] = defaultdict(set)

    for scope_name, scope in project.scopes.items():
        for calc_name, calc in scope.calculations.items():
            for dep_ppath in calc.dep_ppaths.values():
                for output_parts in iter_leaf_path_parts(calc.output_type):
                    output_ppath = ProjectPath(
                        scope=scope_name,
                        path=CalcPath(root=f"@{calc_name}", parts=output_parts),
                    )
                    dependencies_dd[dep_ppath].add(output_ppath)

        for verif_name, verif in scope.verifications.items():
            for dep_ppath in verif.dep_ppaths.values():
                output_ppath = ProjectPath(
                    scope=scope_name,
                    path=VerificationPath(root=f"?{verif_name}"),
                )
                dependencies_dd[dep_ppath].add(output_ppath)

    return dict(dependencies_dd)

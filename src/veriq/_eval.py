import logging
from typing import TYPE_CHECKING, Any

from ._build import build_dependencies_graph
from ._path import (
    CalcPath,
    ModelPath,
    ProjectPath,
    VerificationPath,
    get_value_by_parts,
    hydrate_value_by_leaf_values,
    iter_leaf_path_parts,
)
from ._utils import topological_sort

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pydantic import BaseModel

    from ._models import Project

logger = logging.getLogger(__name__)


def evaluate_project(project: Project, model_data: Mapping[str, BaseModel]) -> dict[ProjectPath, Any]:  # noqa: C901
    result: dict[ProjectPath, Any] = {}
    for scope_name, scope_data in model_data.items():
        root_model = project.scopes[scope_name].get_root_model()
        for leaf_path_parts in iter_leaf_path_parts(root_model):
            leaf_path = ProjectPath(
                scope=scope_name,
                path=ModelPath(root="$", parts=leaf_path_parts),
            )
            value = get_value_by_parts(scope_data, leaf_path_parts)
            result[leaf_path] = value

    logger.debug("Result after hydrated with model data:")
    for ppath, value in result.items():
        logger.debug(f"  {ppath}: {value!r}")

    dependencies_graph = build_dependencies_graph(project)
    eval_order = topological_sort(dependencies_graph.successors)

    for ppath in eval_order:
        if ppath in result:
            continue
        logger.debug(f"Evaluating {ppath}")

        predecessors = dependencies_graph.predecessors[ppath]
        predecessor_values = {pred_ppath: result[pred_ppath] for pred_ppath in predecessors}

        if isinstance(ppath.path, CalcPath):
            calc_scope = project.scopes[ppath.scope]
            calc = calc_scope.calculations[ppath.path.calc_name]
            input_values: dict[str, Any] = {}
            for dep_name, dep_ppath in calc.dep_ppaths.items():
                logger.debug(f"  Hydrating input '{dep_name}' from {dep_ppath}")
                input_values[dep_name] = hydrate_value_by_leaf_values(
                    project.get_type(dep_ppath),
                    {
                        leaf_parts: predecessor_values[
                            ProjectPath(
                                scope=dep_ppath.scope,
                                path=CalcPath(root=dep_ppath.path.root, parts=dep_ppath.path.parts + leaf_parts)
                                if isinstance(dep_ppath.path, CalcPath)
                                else ModelPath(root="$", parts=dep_ppath.path.parts + leaf_parts),
                            )
                        ]
                        for leaf_parts in iter_leaf_path_parts(project.get_type(dep_ppath))
                    },
                )
            logger.debug(f"  Calling calculation {calc.name} with inputs: {input_values}")
            calc_output = calc.func(**input_values)
            logger.debug(f"  Calculation output: {calc_output!r}")
            for leaf_parts in iter_leaf_path_parts(calc.output_type):
                leaf_ppath = ProjectPath(
                    scope=ppath.scope,
                    path=CalcPath(root=ppath.path.root, parts=leaf_parts),
                )
                value = get_value_by_parts(calc_output, leaf_parts)
                logger.debug(f"    Setting output leaf {leaf_ppath} = {value!r}")
                result[leaf_ppath] = value
        elif isinstance(ppath.path, VerificationPath):
            verif_scope = project.scopes[ppath.scope]
            verif = verif_scope.verifications[ppath.path.verification_name]
            input_values = {}
            for dep_name, dep_ppath in verif.dep_ppaths.items():
                logger.debug(f"  Hydrating input '{dep_name}' from {dep_ppath}")
                input_values[dep_name] = hydrate_value_by_leaf_values(
                    project.get_type(dep_ppath),
                    {
                        leaf_parts: predecessor_values[
                            ProjectPath(
                                scope=dep_ppath.scope,
                                path=CalcPath(root=dep_ppath.path.root, parts=dep_ppath.path.parts + leaf_parts)
                                if isinstance(dep_ppath.path, CalcPath)
                                else ModelPath(root="$", parts=dep_ppath.path.parts + leaf_parts),
                            )
                        ]
                        for leaf_parts in iter_leaf_path_parts(project.get_type(dep_ppath))
                    },
                )
            logger.debug(f"  Calling verification {verif.name} with inputs: {input_values}")
            verif_result = verif.func(**input_values)
            logger.debug(f"  Verification result: {verif_result!r}")
            result[ppath] = verif_result
        else:
            msg = f"Unsupported path type for evaluation: {type(ppath.path)}"
            raise TypeError(msg)

    return result

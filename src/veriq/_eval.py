import logging
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from ._build import build_dependencies_graph
from ._models import Project
from ._path import CalcPath, ModelPath, ProjectPath, VerificationPath, get_value_by_parts, iter_leaf_path_parts
from ._utils import topological_sort

logger = logging.getLogger(__name__)


def evaluate_project(project: Project, model_data: Mapping[str, BaseModel]) -> dict[ProjectPath, Any]:
    result: dict[ProjectPath, Any] = {}
    for scope_name, scope_data in model_data.items():
        root_model = project.scopes[scope_name]._root_model
        if root_model is None:
            continue
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
            # FIXME: We should reconstruct the Pydantic model for input values here.
            input_values = {dep_name: predecessor_values[dep_ppath] for dep_name, dep_ppath in calc.dep_ppaths.items()}
            calc_output = calc.func(**input_values)
            for leaf_parts in iter_leaf_path_parts(calc.output_type):
                leaf_abs_parts = ppath.path.parts + leaf_parts
                leaf_ppath = ProjectPath(
                    scope=ppath.scope,
                    path=CalcPath(root=ppath.path.root, parts=leaf_abs_parts),
                )
                value = get_value_by_parts(calc_output, leaf_parts)
                result[leaf_ppath] = value
        elif isinstance(ppath.path, VerificationPath):
            verif_scope = project.scopes[ppath.scope]
            verif = verif_scope.verifications[ppath.path.verification_name]
            input_values = {dep_name: predecessor_values[dep_ppath] for dep_name, dep_ppath in verif.dep_ppaths.items()}
            verif_result = verif.func(**input_values)
            result[ppath] = verif_result
        else:
            msg = f"Unsupported path type for evaluation: {type(ppath.path)}"
            raise TypeError(msg)

    return result

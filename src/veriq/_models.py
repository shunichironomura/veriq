from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Self, get_args

from pydantic import BaseModel, create_model
from scoped_context import NoContextError, ScopedContext, get_current_context
from typing_extensions import _AnnotatedAlias

from ._utils import model_to_flat_dict

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

logger = logging.getLogger(__name__)


def get_deps_from_signature(sig: inspect.Signature) -> dict[str, Depends]:
    """Extract model types from the function signature."""

    def _get_dep_from_annotation(
        annotations: _AnnotatedAlias,
    ) -> Depends | None:
        args = get_args(annotations)
        try:
            return next(iter(arg for arg in args if isinstance(arg, Depends)))
        except StopIteration:
            return None

    return {
        param.name: dep
        for param in sig.parameters.values()
        if (dep := _get_dep_from_annotation(param.annotation)) is not None
    }


def get_models_from_signature(
    sig: inspect.Signature,
) -> dict[str, type[BaseModel]]:
    """Extract model types from the function signature."""
    return {
        param.name: param.annotation
        for param in sig.parameters.values()
        if isinstance(param.annotation, type) and issubclass(param.annotation, BaseModel)
    }


@dataclass
class Calculation[T, **P]:
    """A class to represent a calculation in the verification process."""

    name: str
    func: Callable[P, T]
    model_deps: dict[str, type[BaseModel]] = field(default_factory=dict, repr=False)
    calc_deps: dict[str, Depends] = field(default_factory=dict, repr=False)

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T:
        return self.func(*args, **kwargs)

    def iter_all_model_deps(self) -> Iterable[type[BaseModel]]:
        """Iterate over all model dependencies."""
        yield from self.model_deps.values()
        for calc_dep in self.calc_deps.values():
            yield from calc_dep.calculation.iter_all_model_deps()

    def eval(self, design: dict[str, BaseModel]) -> T:
        """Evaluate the calculation against a design."""
        model_args = {name: design[model.__name__] for name, model in self.model_deps.items()}
        calc_args = {name: calc_dep.calculation.eval(design) for name, calc_dep in self.calc_deps.items()}
        return self.func(**model_args, **calc_args)  # type: ignore[call-arg,arg-type]


@dataclass
class Verification[**P]:
    """A class to represent a verification in the verification process."""

    name: str
    func: Callable[P, bool] = field(repr=False)  # TODO: disallow positional-only arguments
    model_deps: dict[str, type[BaseModel]] = field(default_factory=dict, repr=False)
    calc_deps: dict[str, Depends] = field(default_factory=dict, repr=False)

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> bool:
        return self.func(*args, **kwargs)

    def iter_all_model_deps(self) -> Iterable[type[BaseModel]]:
        """Iterate over all model dependencies."""
        yield from self.model_deps.values()
        for calc_dep in self.calc_deps.values():
            yield from calc_dep.calculation.iter_all_model_deps()

    def eval(self, design: dict[str, BaseModel]) -> bool:
        """Evaluate the verification against a design."""
        model_args = {name: design[model.__name__] for name, model in self.model_deps.items()}
        calc_args = {name: calc_dep.calculation.eval(design) for name, calc_dep in self.calc_deps.items()}
        return self.func(**model_args, **calc_args)  # type: ignore[call-arg,arg-type]


@dataclass
class Requirement(ScopedContext):
    def __post_init__(self) -> None:
        current_scope_or_requirement = get_current_context((Scope, Requirement))
        if isinstance(current_scope_or_requirement, Scope):
            current_scope_or_requirement.add_requirement(self)
        elif isinstance(current_scope_or_requirement, Requirement):
            current_scope_or_requirement.decomposed_requirements.append(self)

    description: str
    decomposed_requirements: list[Requirement] = field(default_factory=list, repr=False)
    verified_by: Verification[...] | None = None
    depends_on: list[Requirement] = field(default_factory=list, repr=False)

    def iter_requirements(self, *, depth: int | None = None, leaf_only: bool = False) -> Iterable[Requirement]:
        """Iterate over requirements under the current requirement."""
        if not leaf_only or not self.decomposed_requirements:
            yield self
        if depth is not None and depth <= 0:
            return
        for req in self.decomposed_requirements:
            yield from req.iter_requirements(depth=depth - 1 if depth is not None else None, leaf_only=leaf_only)

    def __enter__(self) -> Self:
        super().__enter__()
        logger.debug(f"Entering requirement: {self.description}")
        current_scope = Scope.current()
        logger.debug(f"Current scope: {current_scope.name}")
        try:
            next(iter(req for _, req in current_scope.iter_requirements(include_child_scopes=False) if req == self))

        except StopIteration:
            msg = f"The entered requirement '{self.description}' doesn't belong to the current scope."
            raise RuntimeError(msg) from None

        return self


@dataclass
class ModelCompatibility[MA: BaseModel, MB: BaseModel]:
    """A class to represent model compatibility in the verification process."""

    model_a: type[MA]
    model_b: type[MB]
    func: Callable[[MA, MB], bool] = field(repr=False)


@dataclass
class Scope(ScopedContext):
    name: str
    requirements: list[Requirement] = field(default_factory=list)
    child_scopes: list[Scope] = field(default_factory=list)
    model_compatibilities: list[ModelCompatibility[Any, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        try:
            parent_scope = Scope.current()
        except NoContextError:
            pass
        else:
            parent_scope.child_scopes.append(self)

    def iter_requirements(
        self,
        *,
        depth: int | None = None,
        include_child_scopes: bool = False,
        leaf_only: bool = False,
    ) -> Iterable[tuple[tuple[str, ...], Requirement]]:
        """Iterate over requirements in the scope."""
        for req in self.requirements:
            for req_ in req.iter_requirements(depth=depth, leaf_only=leaf_only):
                yield (self.name,), req_
        if include_child_scopes:
            for child_scope in self.child_scopes:
                for path, req in child_scope.iter_requirements(depth=depth, leaf_only=leaf_only):
                    yield (self.name, *path), req

    def iter_verifications(
        self,
        *,
        include_child_scopes: bool = False,
        leaf_only: bool = True,
    ) -> Iterable[tuple[tuple[str, ...], Verification[...]]]:
        """Iterate over verifications in the scope."""
        # TODO: If multiple requirements are verified by the same verification instance,
        # the verification is now yielded more than once.
        for path, req in self.iter_requirements(include_child_scopes=include_child_scopes, leaf_only=leaf_only):
            if req.verified_by:
                yield (path, req.verified_by)

    def iter_models(
        self,
        *,
        include_child_scopes: bool = False,
        leaf_only: bool = True,
    ) -> Iterable[tuple[tuple[str, ...], type[BaseModel]]]:
        """Iterate over models in the scope."""
        for path, verification in self.iter_verifications(
            include_child_scopes=include_child_scopes,
            leaf_only=leaf_only,
        ):
            for model in verification.iter_all_model_deps():
                yield (path, model)

    def add_requirement(self, requirement: Requirement) -> None:
        """Add a requirement to the scope."""
        self.requirements.append(requirement)

    def model_compatibility[MA: BaseModel, MB: BaseModel](
        self,
        func: Callable[[MA, MB], bool],
        /,
    ) -> Callable[[MA, MB], bool]:
        """Decorator to mark a function as a model compatibility check."""
        sig = inspect.signature(func)
        model_a, model_b = tuple(
            param.annotation
            for param in sig.parameters.values()
            if isinstance(param.annotation, type) and issubclass(param.annotation, BaseModel)
        )

        compatibility = ModelCompatibility(model_a=model_a, model_b=model_b, func=func)  # type: ignore[arg-type]
        self.model_compatibilities.append(compatibility)
        return func

    def design_json_schema(
        self,
        *,
        include_child_scopes: bool = False,
        leaf_only: bool = True,
    ) -> dict[str, Any]:
        """Get the schema of models in the scope."""
        design_model = self.design_model(
            include_child_scopes=include_child_scopes,
            leaf_only=leaf_only,
        )
        return design_model.model_json_schema()

    def design_model(self, *, include_child_scopes: bool = False, leaf_only: bool = True) -> type[BaseModel]:
        """Get the design model for the scope."""
        fields = {
            model.__name__: model for _, model in self.iter_models(include_child_scopes=False, leaf_only=leaf_only)
        }
        if include_child_scopes:
            fields |= {
                child_scope.name: child_scope.design_model(
                    include_child_scopes=include_child_scopes,
                    leaf_only=leaf_only,
                )
                for child_scope in self.child_scopes
            }

        return create_model(  # type: ignore[no-any-return, call-overload]
            f"{self.name}",
            **fields,
        )

    def verify_design(
        self,
        design: dict[str, BaseModel] | BaseModel,
        *,
        include_child_scopes: bool = False,
        leaf_only: bool = True,
    ) -> bool:
        """Verify the design against the scope's requirements."""
        # TODO: Return more detailed verification results.
        fields_in_current_scope = {
            model.__name__ for _, model in self.iter_models(include_child_scopes=False, leaf_only=leaf_only)
        }
        design_dict_full = design if isinstance(design, dict) else model_to_flat_dict(design)
        design_dict = {k: v for k, v in design_dict_full.items() if k in fields_in_current_scope}
        for _, verification in self.iter_verifications(include_child_scopes=False, leaf_only=leaf_only):
            if not verification.eval(design_dict):
                return False

        if include_child_scopes:
            for child_scope in self.child_scopes:
                if not child_scope.verify_design(
                    design_dict_full[child_scope.name],
                    include_child_scopes=include_child_scopes,
                    leaf_only=leaf_only,
                ):
                    return False

        return True


@dataclass
class Depends:
    """A class to represent dependencies between calculations and verifications."""

    calculation: Calculation[Any, ...]

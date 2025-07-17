from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, get_args

from pydantic import BaseModel
from typing_extensions import _AnnotatedAlias

from ._utils import ContextMixin

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


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
        return self.func(**model_args, **calc_args)


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
        return self.func(**model_args, **calc_args)


@dataclass
class Requirement(ContextMixin):
    def __post_init__(self) -> None:
        for scope_or_requirement in ContextMixin.global_stack_queue()[::-1]:
            if isinstance(scope_or_requirement, Scope):
                scope_or_requirement.add_requirement(self)
                break
            if isinstance(scope_or_requirement, Requirement):
                scope_or_requirement.decomposed_requirements.append(self)
                break
        else:
            # If no scope or requirement was found, we could log a warning or handle it accordingly.
            pass

    description: str
    decomposed_requirements: list[Requirement] = field(default_factory=list, repr=False)
    verified_by: Verification[[BaseModel]] | None = None

    def iter_requirements(self, *, depth: int | None = None) -> Iterable[Requirement]:
        """Iterate over requirements in the current context."""
        yield self
        if depth is not None and depth <= 0:
            return
        for req in self.decomposed_requirements:
            yield from req.iter_requirements(depth=depth - 1 if depth is not None else None)

    def iter_leaf_requirements(self) -> Iterable[Requirement]:
        """Iterate over leaf requirements in the current context."""
        if not self.decomposed_requirements:
            yield self
        else:
            for req in self.decomposed_requirements:
                yield from req.iter_leaf_requirements()


@dataclass
class ModelCompatibility[MA: BaseModel, MB: BaseModel]:
    """A class to represent model compatibility in the verification process."""

    model_a: type[MA]
    model_b: type[MB]
    func: Callable[[MA, MB], bool] = field(repr=False)


@dataclass
class Scope(ContextMixin):
    name: str
    requirements: list[Requirement] = field(default_factory=list)
    child_scopes: list[Scope] = field(default_factory=list)
    model_compatibilities: list[ModelCompatibility] = field(default_factory=list)

    def iter_requirements(
        self,
        *,
        depth: int | None = None,
        include_child_scopes: bool = False,
    ) -> Iterable[Requirement]:
        """Iterate over requirements in the scope."""
        for req in self.requirements:
            yield from req.iter_requirements(depth=depth)
        if include_child_scopes:
            for child_scope in self.child_scopes:
                yield from child_scope.iter_requirements(depth=depth)

    def iter_leaf_requirements(self, *, include_child_scopes: bool = False) -> Iterable[Requirement]:
        """Iterate over leaf requirements in the scope."""
        for req in self.requirements:
            yield from req.iter_leaf_requirements()
        if include_child_scopes:
            for child_scope in self.child_scopes:
                yield from child_scope.iter_leaf_requirements()

    def iter_verifications(
        self,
        *,
        include_child_scopes: bool = False,
        leaf_only: bool = True,
    ) -> Iterable[Verification]:
        """Iterate over verifications in the scope."""
        iterator = (
            self.iter_leaf_requirements(include_child_scopes=include_child_scopes)
            if leaf_only
            else self.iter_requirements(include_child_scopes=include_child_scopes)
        )
        for req in iterator:
            if req.verified_by:
                yield req.verified_by
        if include_child_scopes:
            for child_scope in self.child_scopes:
                yield from child_scope.iter_verifications(
                    include_child_scopes=include_child_scopes,
                    leaf_only=leaf_only,
                )

    def iter_models(self, *, include_child_scopes: bool = False, leaf_only: bool = True) -> Iterable[type[BaseModel]]:
        """Iterate over models in the scope."""
        for verification in self.iter_verifications(
            include_child_scopes=include_child_scopes,
            leaf_only=leaf_only,
        ):
            yield from verification.iter_all_model_deps()

    def add_requirement(self, requirement: Requirement) -> None:
        """Add a requirement to the scope."""
        self.requirements.append(requirement)

    def model_compatibility[MA: BaseModel, MB: BaseModel](
        self,
        func: Callable[[MA, MB], bool],
        /,
    ) -> ModelCompatibility[MA, MB]:
        """Decorator to mark a function as a model compatibility check."""
        sig = inspect.signature(func)
        model_a, model_b = tuple(
            param.annotation
            for param in sig.parameters.values()
            if isinstance(param.annotation, type) and issubclass(param.annotation, BaseModel)
        )

        compatibility = ModelCompatibility(model_a=model_a, model_b=model_b, func=func)
        self.model_compatibilities.append(compatibility)
        return compatibility

    def model_schema(self, *, include_child_scopes: bool = False, leaf_only: bool = True) -> dict[str, type[BaseModel]]:
        """Get the schema of models in the scope."""
        return {
            model.__name__: model
            for model in self.iter_models(include_child_scopes=include_child_scopes, leaf_only=leaf_only)
        }

    def verify_design(
        self,
        design: dict[str, BaseModel],
        *,
        include_child_scopes: bool = False,
        leaf_only: bool = True,
    ) -> bool:
        """Verify the design against the scope's requirements."""
        for verification in self.iter_verifications(
            include_child_scopes=include_child_scopes,
            leaf_only=leaf_only,
        ):
            if not verification.eval(design):
                return False
        return True


@dataclass
class Depends:
    """A class to represent dependencies between calculations and verifications."""

    calculation: Calculation

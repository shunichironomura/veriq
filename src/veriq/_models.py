from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Self, get_args

from pydantic import BaseModel
from scoped_context import ScopedContext, get_current_context
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


@dataclass(slots=True)
class Project:
    """A class to hold the scopes."""

    name: str
    _scopes: dict[str, Scope] = field(default_factory=dict, repr=False)

    def add_scope(self, scope: Scope) -> None:
        """Add a scope to the project."""
        if scope.name in self._scopes:
            msg = f"Scope with name '{scope.name}' already exists in the project."
            raise KeyError(msg)
        self._scopes[scope.name] = scope


@dataclass(slots=True)
class Calculation[T, **P]:
    """A class to represent a calculation in the verification process."""

    name: str
    func: Callable[P, T]
    imported_scope_names: list[str] = field(default_factory=list, repr=False)
    deps: dict[str, Any] = field(default_factory=dict, repr=False)

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T:
        return self.func(*args, **kwargs)


@dataclass(slots=True)
class Verification[**P]:
    """A class to represent a verification in the verification process."""

    name: str
    func: Callable[P, bool] = field(repr=False)  # TODO: disallow positional-only arguments
    model_deps: dict[str, type[BaseModel]] = field(default_factory=dict, repr=False)
    calc_deps: dict[str, Depends] = field(default_factory=dict, repr=False)
    imported_scope_names: list[str] = field(default_factory=list, repr=False)

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> bool:
        return self.func(*args, **kwargs)


@dataclass(slots=True)
class Requirement(ScopedContext):
    def __post_init__(self) -> None:
        current_scope_or_requirement = get_current_context((Scope, Requirement))
        if isinstance(current_scope_or_requirement, Scope):
            current_scope_or_requirement.add_requirement(self)
        elif isinstance(current_scope_or_requirement, Requirement):
            current_scope_or_requirement.decomposed_requirements.append(self)

    id: str
    description: str
    decomposed_requirements: list[Requirement] = field(default_factory=list, repr=False)
    verified_by: Verification | None = None
    depends_on: list[Requirement] = field(default_factory=list, repr=False)

    def iter_requirements(self, *, depth: int | None = None, leaf_only: bool = False) -> Iterable[Requirement]:
        """Iterate over requirements under the current requirement."""
        if not leaf_only or not self.decomposed_requirements:
            yield self
        if depth is not None and depth <= 0:
            return
        for req in self.decomposed_requirements:
            yield from req.iter_requirements(depth=depth - 1 if depth is not None else None, leaf_only=leaf_only)


@dataclass(slots=True)
class Scope(ScopedContext):
    name: str
    _subscopes: list[Scope] = field(default_factory=list)
    _root_model: type[BaseModel] | None = None
    _requirements: list[Requirement] = field(default_factory=list)
    _verifications: list[Verification] = field(default_factory=list)
    _calculations: list[Calculation] = field(default_factory=list)

    def add_subscope(self, scope: Scope) -> None:
        """Add a subscope to the current scope."""
        self._subscopes.append(scope)

    def root_model[M: type[BaseModel]](self) -> Callable[[M], M]:
        """Decorator to mark a model as the root model of the scope."""

        def decorator(model: M) -> M:
            if self._root_model is not None:
                msg = f"Scope '{self.name}' already has a root model assigned: {self._root_model.__name__}"
                raise RuntimeError(msg)
            self._root_model = model
            return model

        return decorator

    def verification(self, imports: Iterable[str] = ()) -> Callable[[Callable], Verification]:
        """Decorator to mark a function as a verification in the scope."""

        def decorator(func: Callable) -> Verification:
            sig = inspect.signature(func)
            model_deps = get_models_from_signature(sig)
            calc_deps = get_deps_from_signature(sig)
            if not hasattr(func, "__name__") or not isinstance(func.__name__, str):
                msg = "Function must have a valid name."
                raise TypeError(msg)
            verification = Verification(
                name=func.__name__,
                func=func,
                deps={},
                # model_deps=model_deps,
                # calc_deps=calc_deps,
                imported_scope_names=list(imports),
            )
            self._verifications.append(verification)
            return verification

        return decorator

    def calculation(self, imports: Iterable[str] = ()) -> Callable[[Callable], Calculation]:
        """Decorator to mark a function as a calculation in the scope."""

        def decorator(func: Callable) -> Calculation:
            sig = inspect.signature(func)
            calc_deps = get_deps_from_signature(sig)
            if not hasattr(func, "__name__") or not isinstance(func.__name__, str):
                msg = "Function must have a valid name."
                raise TypeError(msg)
            calculation = Calculation(
                name=func.__name__,
                func=func,
                model_deps=model_deps,
                calc_deps=calc_deps,
                imported_scope_names=list(imports),
            )
            self._calculations.append(calculation)
            return calculation

        return decorator

    def requirement(self, id: str, description: str, verified_by: Iterable[Verification] = ()) -> Requirement:
        """Create and add a requirement to the scope."""
        requirement = Requirement(description=description, verified_by=next(iter(verified_by), None))
        self._requirements.append(requirement)
        return requirement

    def fetch_requirement(self, /, _id: str) -> Requirement:
        """Fetch a requirement by its ID."""
        for req in self._requirements:
            if req.description == _id:
                return req
        msg = f"Requirement with ID '{_id}' not found in scope '{self.name}'."
        raise KeyError(msg)

    def add_requirement(self, requirement: Requirement) -> None:
        """Add a requirement to the scope."""
        self._requirements.append(requirement)

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
            for child_scope in self._subscopes:
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

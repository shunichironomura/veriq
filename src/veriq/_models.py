from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, get_args

from pydantic import BaseModel
from scoped_context import ScopedContext, get_current_context
from typing_extensions import _AnnotatedAlias

from ._path import ModelPath
from ._utils import model_to_flat_dict

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

logger = logging.getLogger(__name__)


def _get_deps_from_signature(sig: inspect.Signature) -> dict[str, Calc | Fetch]:
    """Extract Calc or Fetch annotation from the function signature."""

    def _get_dep_from_annotation(
        annotations: _AnnotatedAlias,
    ) -> Calc | Fetch | None:
        args = get_args(annotations)
        try:
            return next(iter(arg for arg in args if isinstance(arg, (Fetch, Calc))))
        except StopIteration:
            return None

    return {
        param.name: dep
        for param in sig.parameters.values()
        if (dep := _get_dep_from_annotation(param.annotation)) is not None
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
class Calc:
    """Reference to a calculation."""

    name: str
    path: str
    scope: str | None = None
    _model_path: ModelPath = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._model_path = ModelPath.parse(self.path)


@dataclass(slots=True)
class Fetch:
    """Reference to a path in a model."""

    path: str
    scope: str | None = None
    _model_path: ModelPath = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._model_path = ModelPath.parse(self.path)


@dataclass(slots=True)
class Calculation[T, **P]:
    """A class to represent a calculation in the verification process."""

    name: str
    func: Callable[P, T]
    deps: dict[str, Fetch | Calc] = field(default_factory=dict, repr=False)
    imported_scope_names: list[str] = field(default_factory=list, repr=False)

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T:
        return self.func(*args, **kwargs)


@dataclass(slots=True)
class Verification[**P]:
    """A class to represent a verification in the verification process."""

    name: str
    func: Callable[P, bool] = field(repr=False)  # TODO: disallow positional-only arguments
    deps: dict[str, Fetch | Calc] = field(default_factory=dict, repr=False)
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
    verified_by: list[Verification] = field(default_factory=list, repr=False)
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
    _root_model: type[BaseModel] | None = None
    _requirements: dict[str, Requirement] = field(default_factory=dict)
    _verifications: dict[str, Verification] = field(default_factory=dict)
    _calculations: dict[str, Calculation] = field(default_factory=dict)

    def root_model[M: type[BaseModel]](self) -> Callable[[M], M]:
        """Decorator to mark a model as the root model of the scope."""

        def decorator(model: M) -> M:
            if self._root_model is not None:
                msg = f"Scope '{self.name}' already has a root model assigned: {self._root_model.__name__}"
                raise RuntimeError(msg)
            self._root_model = model
            return model

        return decorator

    def verification(self, name: str | None = None, imports: Iterable[str] = ()) -> Callable[[Callable], Verification]:
        """Decorator to mark a function as a verification in the scope."""

        def decorator(func: Callable) -> Verification:
            sig = inspect.signature(func)
            deps = _get_deps_from_signature(sig)
            if name is None:
                if not hasattr(func, "__name__") or not isinstance(func.__name__, str):
                    msg = "Function must have a valid name."
                    raise TypeError(msg)
                verification_name = func.__name__
            else:
                verification_name = name
            verification = Verification(
                name=verification_name,
                func=func,
                deps=deps,
                imported_scope_names=list(imports),
            )
            if verification_name in self._verifications:
                msg = f"Verification with name '{verification_name}' already exists in scope '{self.name}'."
                raise KeyError(msg)
            self._verifications[verification_name] = verification
            return verification

        return decorator

    def calculation(self, name: str | None = None, imports: Iterable[str] = ()) -> Callable[[Callable], Calculation]:
        """Decorator to mark a function as a calculation in the scope."""

        def decorator(func: Callable) -> Calculation:
            sig = inspect.signature(func)
            deps = _get_deps_from_signature(sig)
            if name is None:
                if not hasattr(func, "__name__") or not isinstance(func.__name__, str):
                    msg = "Function must have a valid name."
                    raise TypeError(msg)
                calculation_name = func.__name__
            else:
                calculation_name = name
            calculation = Calculation(
                name=calculation_name,
                func=func,
                deps=deps,
                imported_scope_names=list(imports),
            )
            if calculation_name in self._calculations:
                msg = f"Calculation with name '{calculation_name}' already exists in scope '{self.name}'."
                raise KeyError(msg)
            self._calculations[calculation_name] = calculation
            return calculation

        return decorator

    def requirement(self, id_: str, /, description: str, verified_by: Iterable[Verification] = ()) -> Requirement:
        """Create and add a requirement to the scope."""
        requirement = Requirement(description=description, verified_by=list(verified_by), id=id_)
        self.add_requirement(requirement)
        return requirement

    def fetch_requirement(self, id_: str, /) -> Requirement:
        """Fetch a requirement by its ID."""
        try:
            return self._requirements[id_]
        except KeyError as e:
            msg = f"Requirement with ID '{id_}' not found in scope '{self.name}'."
            raise KeyError(msg) from e

    def add_requirement(self, requirement: Requirement) -> None:
        """Add an existing requirement to the scope."""
        if requirement.id in self._requirements:
            msg = f"Requirement with ID '{requirement.id}' already exists in scope '{self.name}'."
            raise KeyError(msg)
        self._requirements[requirement.id] = requirement

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

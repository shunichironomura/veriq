from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, get_args

from pydantic import BaseModel
from scoped_context import NoContextError, ScopedContext
from typing_extensions import _AnnotatedAlias

from ._path import ModelPath

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
        try:
            current_requirement = Requirement.current()
        except NoContextError:
            current_requirement = None
        else:
            current_requirement.decomposed_requirements.append(self)

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
class Scope:
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
            if name is None:
                if not hasattr(func, "__name__") or not isinstance(func.__name__, str):
                    msg = "Function must have a valid name."
                    raise TypeError(msg)
                verification_name = func.__name__
            else:
                verification_name = name

            sig = inspect.signature(func)
            deps = _get_deps_from_signature(sig)
            for dep_name, dep in deps.items():
                if dep.scope is None:
                    dep.scope = self.name
                if dep.scope != self.name and dep.scope not in imports:
                    msg = (
                        f"Dependency '{dep_name}' is from scope '{dep.scope}',"
                        f" which is not imported in verification '{verification_name}'."
                    )
                    raise ValueError(msg)

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
            if name is None:
                if not hasattr(func, "__name__") or not isinstance(func.__name__, str):
                    msg = "Function must have a valid name."
                    raise TypeError(msg)
                calculation_name = func.__name__
            else:
                calculation_name = name

            sig = inspect.signature(func)
            deps = _get_deps_from_signature(sig)
            for dep_name, dep in deps.items():
                if dep.scope is None:
                    dep.scope = self.name
                if dep.scope != self.name and dep.scope not in imports:
                    msg = (
                        f"Dependency '{dep_name}' is from scope '{dep.scope}',"
                        f" which is not imported in calculation '{calculation_name}'."
                    )
                    raise ValueError(msg)

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
        if id_ in self._requirements:
            msg = f"Requirement with ID '{id_}' already exists in scope '{self.name}'."
            raise KeyError(msg)
        self._requirements[id_] = requirement
        return requirement

    def fetch_requirement(self, id_: str, /) -> Requirement:
        """Fetch a requirement by its ID."""
        try:
            return self._requirements[id_]
        except KeyError as e:
            msg = f"Requirement with ID '{id_}' not found in scope '{self.name}'."
            raise KeyError(msg) from e

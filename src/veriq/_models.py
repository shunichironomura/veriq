from __future__ import annotations

import inspect
import logging
from annotationlib import ForwardRef
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, get_args

from pydantic import BaseModel
from scoped_context import NoContextError, ScopedContext
from typing_extensions import _AnnotatedAlias

from ._path import AttributePart, CalcPath, ItemPart, ModelPath, ProjectPath, VerificationPath, parse_path

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

logger = logging.getLogger(__name__)


def _get_dep_refs_from_signature(sig: inspect.Signature) -> dict[str, Ref]:
    """Extract Calc or Fetch annotation from the function signature."""

    def _get_dep_ref_from_annotation(
        name: str,
        annotations: _AnnotatedAlias,
    ) -> Ref | None:
        args = get_args(annotations)
        try:
            return next(iter(arg for arg in args if isinstance(arg, Ref)))
        except StopIteration:
            msg = f"Parameter '{name}' must be annotated with Fetch or Calc."
            raise TypeError(msg) from None

    return {
        param.name: dep
        for param in sig.parameters.values()
        if (dep := _get_dep_ref_from_annotation(param.name, param.annotation)) is not None
    }


def _get_return_type_from_signature(sig: inspect.Signature) -> type:
    """Extract return type from the function signature."""
    return_annotation = sig.return_annotation
    if return_annotation is inspect.Signature.empty:
        msg = "Function must have a return type annotation."
        raise TypeError(msg)
    if isinstance(return_annotation, type):
        return return_annotation
    msg = "Return type must be a type."
    raise TypeError(msg)


@dataclass(slots=True)
class Project:
    """A class to hold the scopes."""

    name: str
    _scopes: dict[str, Scope] = field(default_factory=dict)

    def add_scope(self, scope: Scope) -> None:
        """Add a scope to the project."""
        if scope.name in self._scopes:
            msg = f"Scope with name '{scope.name}' already exists in the project."
            raise KeyError(msg)
        self._scopes[scope.name] = scope

    @property
    def scopes(self) -> dict[str, Scope]:
        """Get all scopes in the project."""
        return self._scopes

    def get_type(self, ppath: ProjectPath) -> type:
        """Get the type of the given project path."""
        scope = self._scopes.get(ppath.scope)
        if scope is None:
            msg = f"Scope '{ppath.scope}' not found in project '{self.name}'."
            raise KeyError(msg)

        if isinstance(ppath.path, ModelPath):
            if scope._root_model is None:
                msg = f"Scope '{scope.name}' does not have a root model defined."
                raise RuntimeError(msg)
            current_type: type = scope._root_model
            for part in ppath.path.parts:
                if isinstance(current_type, ForwardRef):
                    current_type = current_type.evaluate()
                match part:
                    case AttributePart(name):
                        try:
                            field_info = current_type.model_fields[name]
                        except KeyError as e:
                            msg = f"Attribute '{name}' not found in model '{current_type.__name__}'."
                            raise KeyError(msg) from e
                        current_type = field_info.annotation
                    case ItemPart(key):
                        args = get_args(current_type)
                        if len(args) != 2:
                            msg = f"Type '{current_type}' is not subscriptable with key '{key}'."
                            raise TypeError(msg)
                        current_type = args[1]  # type: ignore[assignment]
                    case _:
                        msg = f"Unknown part type: {type(part)}"
                        raise TypeError(msg)

            if isinstance(current_type, ForwardRef):
                current_type = current_type.evaluate()

            return current_type

        if isinstance(ppath.path, CalcPath):
            calc_name = ppath.path.root.lstrip(ppath.path.PREFIX)
            calculation = scope.calculations.get(calc_name)
            if calculation is None:
                msg = f"Calculation '{calc_name}' not found in scope '{scope.name}'."
                raise KeyError(msg)
            return calculation.output_type

        if isinstance(ppath.path, VerificationPath):
            return bool

        msg = f"Unsupported path type: {ppath.path.__class__.__name__}"
        raise TypeError(msg)


@dataclass(slots=True)
class Ref:
    """Reference to a project path."""

    path: str
    scope: str | None = None


@dataclass(slots=True)
class Calculation[T, **P]:
    """A class to represent a calculation in the verification process."""

    name: str
    func: Callable[P, T] = field(repr=False)
    default_scope_name: str = field()
    imported_scope_names: list[str] = field(default_factory=list)
    assumed_verifications: list[Verification] = field(default_factory=list)

    # Fields initialized in __post_init__
    dep_ppaths: dict[str, ProjectPath] = field(init=False)
    output_type: type[T] = field(init=False)

    def __post_init__(self) -> None:
        sig = inspect.signature(self.func)
        dep_refs = _get_dep_refs_from_signature(sig)

        def ref_to_project_path(ref: Ref) -> ProjectPath:
            scope_name = self.default_scope_name if ref.scope is None else ref.scope
            return ProjectPath(scope=scope_name, path=parse_path(ref.path))

        for dep_name, dep_ref in dep_refs.items():
            if dep_ref.scope is None:
                dep_ref.scope = self.default_scope_name
            if dep_ref.scope != self.default_scope_name and dep_ref.scope not in self.imported_scope_names:
                msg = (
                    f"Dependency '{dep_name}' is from scope '{dep_ref.scope}',"
                    f" which is not imported in calculation '{self.name}'."
                )
                raise ValueError(msg)
        self.dep_ppaths = {name: ref_to_project_path(ref) for name, ref in dep_refs.items()}
        self.output_type = _get_return_type_from_signature(sig)

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T:
        return self.func(*args, **kwargs)


@dataclass(slots=True)
class Verification[**P]:
    """A class to represent a verification in the verification process."""

    name: str
    func: Callable[P, bool] = field(repr=False)  # TODO: disallow positional-only arguments
    default_scope_name: str = field()
    imported_scope_names: list[str] = field(default_factory=list)
    assumed_verifications: list[Verification] = field(default_factory=list)

    # Fields initialized in __post_init__
    dep_ppaths: dict[str, ProjectPath] = field(init=False)

    def __post_init__(self) -> None:
        sig = inspect.signature(self.func)
        dep_refs = _get_dep_refs_from_signature(sig)

        def ref_to_project_path(ref: Ref) -> ProjectPath:
            scope_name = self.default_scope_name if ref.scope is None else ref.scope
            return ProjectPath(scope=scope_name, path=parse_path(ref.path))

        for dep_name, dep_ref in dep_refs.items():
            if dep_ref.scope is None:
                dep_ref.scope = self.default_scope_name
            if dep_ref.scope != self.default_scope_name and dep_ref.scope not in self.imported_scope_names:
                msg = (
                    f"Dependency '{dep_name}' is from scope '{dep_ref.scope}',"
                    f" which is not imported in verification '{self.name}'."
                )
                raise ValueError(msg)
        self.dep_ppaths = {name: ref_to_project_path(ref) for name, ref in dep_refs.items()}

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
    _root_model: type[BaseModel] | None = field(default=None)
    _requirements: dict[str, Requirement] = field(default_factory=dict)
    _verifications: dict[str, Verification] = field(default_factory=dict)
    _calculations: dict[str, Calculation] = field(default_factory=dict)

    @property
    def requirements(self) -> dict[str, Requirement]:
        """Get all requirements in the scope."""
        return self._requirements

    @property
    def verifications(self) -> dict[str, Verification]:
        """Get all verifications in the scope."""
        return self._verifications

    @property
    def calculations(self) -> dict[str, Calculation]:
        """Get all calculations in the scope."""
        return self._calculations

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

            assumed_verifications: list[Verification] = []
            if hasattr(func, "__veriq_assumed_verifications__"):
                assumed_verifications = func.__veriq_assumed_verifications__

            verification = Verification(
                name=verification_name,
                func=func,
                imported_scope_names=list(imports),
                assumed_verifications=assumed_verifications,
                default_scope_name=self.name,
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

            assumed_verifications: list[Verification] = []
            if hasattr(func, "__veriq_assumed_verifications__"):
                assumed_verifications = func.__veriq_assumed_verifications__

            calculation = Calculation(
                name=calculation_name,
                func=func,
                imported_scope_names=list(imports),
                assumed_verifications=assumed_verifications,
                default_scope_name=self.name,
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

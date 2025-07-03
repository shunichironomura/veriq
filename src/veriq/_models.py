from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Literal, Self

if TYPE_CHECKING:
    from collections.abc import Iterable
    from types import TracebackType


@dataclass
class Calculation: ...


@dataclass
class Verification: ...


class ContextMixin:
    """A mixin class for context management."""

    _thread_local: ClassVar[threading.local]

    def __init_subclass__(cls, *args: object, **kwargs: object) -> None:
        super().__init_subclass__(*args, **kwargs)
        cls._thread_local = threading.local()

    @classmethod
    def _get_stack(cls) -> queue.LifoQueue[Self]:
        if not hasattr(cls._thread_local, "stack"):
            cls._thread_local.stack = queue.LifoQueue()
        return cls._thread_local.stack  # type: ignore[no-any-return]

    @classmethod
    def current(cls) -> Self | None:
        if cls._get_stack().qsize() == 0:
            return None
        return cls._get_stack().queue[-1]

    def __enter__(self) -> Self:
        self._get_stack().put(self, block=False)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._get_stack().get(block=False)


@dataclass
class Requirement(ContextMixin):
    def __post_init__(self) -> None:
        if (current_scope := Scope.current()) is not None:
            current_scope.add_requirement(self)


TRequirementDecompositionLevel = Literal["conservative", "aggressive"]


@dataclass
class DecomposedRequirements(ContextMixin):
    level: TRequirementDecompositionLevel


@dataclass
class Scope(ContextMixin):
    def iter_requirements(self) -> Iterable[Requirement]:
        """Iterate over requirements in the scope."""
        raise NotImplementedError

    def iter_leaf_requirements(self) -> Iterable[Requirement]:
        """Iterate over leaf requirements in the scope."""
        raise NotImplementedError

    def iter_models(self) -> Iterable:
        """Iterate over models in the scope."""
        raise NotImplementedError

    def add_requirement(self, requirement: Requirement) -> None: ...


class Depends: ...

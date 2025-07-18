from __future__ import annotations

import queue
import threading
from typing import TYPE_CHECKING, Any, ClassVar, Self

if TYPE_CHECKING:
    from types import TracebackType

    from pydantic import BaseModel


class ContextMixin:
    """A mixin class for context management."""

    _thread_local: ClassVar[threading.local]
    _thread_local_global: ClassVar[threading.local] = threading.local()  # Shared across all subclasses

    def __init_subclass__(cls, *args: object, **kwargs: object) -> None:
        super().__init_subclass__(*args, **kwargs)
        cls._thread_local = threading.local()

    @classmethod
    def _get_stack(cls) -> queue.LifoQueue[Self]:
        if not hasattr(cls._thread_local, "stack"):
            cls._thread_local.stack = queue.LifoQueue()
        return cls._thread_local.stack  # type: ignore[no-any-return]

    @classmethod
    def _get_global_stack(cls) -> queue.LifoQueue[ContextMixin]:
        if not hasattr(cls._thread_local_global, "stack"):
            cls._thread_local_global.stack = queue.LifoQueue()
        return cls._thread_local_global.stack  # type: ignore[no-any-return]

    @classmethod
    def stack_queue(cls) -> list[Self]:
        """Get the stack queue for the current context."""
        return cls._get_stack().queue

    @classmethod
    def global_stack_queue(cls) -> list[ContextMixin]:
        """Get the global stack queue for the current context."""
        return cls._get_global_stack().queue

    @classmethod
    def current(cls) -> Self | None:
        if cls._get_stack().qsize() == 0:
            return None
        return cls._get_stack().queue[-1]

    @classmethod
    def current_global(cls) -> ContextMixin | None:
        if cls._get_global_stack().qsize() == 0:
            return None
        return cls._get_global_stack().queue[-1]

    def __enter__(self) -> Self:
        self._get_stack().put(self, block=False)
        self._get_global_stack().put(self, block=False)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._get_stack().get(block=False)
        self._get_global_stack().get(block=False)


def model_to_flat_dict(model_instance: BaseModel) -> dict[str, Any]:
    """Convert model to dict without recursive conversion."""
    model = model_instance.__class__
    result = {}
    for field_name in model.model_fields:
        result[field_name] = getattr(model_instance, field_name)
    return result

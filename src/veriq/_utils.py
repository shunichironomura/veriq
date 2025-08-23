from __future__ import annotations

import queue
import threading
from typing import TYPE_CHECKING, Any, ClassVar, Self

if TYPE_CHECKING:
    from types import TracebackType

    from pydantic import BaseModel


class ContextMixin:
    """A mixin class for context management."""

    # Thread-local storage for each subclass
    _thread_local: ClassVar[threading.local]

    # Thread-local storage shared across all subclasses
    _thread_local_classwide: ClassVar[threading.local] = threading.local()

    def __init_subclass__(cls, *args: object, **kwargs: object) -> None:
        super().__init_subclass__(*args, **kwargs)
        cls._thread_local = threading.local()

    @classmethod
    def _stack(cls) -> queue.LifoQueue[Self]:
        if not hasattr(cls._thread_local, "stack"):
            cls._thread_local.stack = queue.LifoQueue()
        return cls._thread_local.stack  # type: ignore[no-any-return]

    @classmethod
    def _classwide_stack(cls) -> queue.LifoQueue[ContextMixin]:
        if not hasattr(cls._thread_local_classwide, "stack"):
            cls._thread_local_classwide.stack = queue.LifoQueue()
        return cls._thread_local_classwide.stack  # type: ignore[no-any-return]

    @classmethod
    def stack_queue(cls) -> list[Self]:
        """Get the stack queue for the current context."""
        return cls._stack().queue

    @classmethod
    def classwide_stack_queue(
        cls,
        class_or_tuple: type[ContextMixin] | tuple[type[ContextMixin], ...] | None = None,
    ) -> list[ContextMixin]:
        """Get the classwide stack queue for the current context.

        If class_or_tuple is provided, filter the queue to only include instances of the specified class or classes.
        """
        if class_or_tuple is not None:
            return [item for item in cls._classwide_stack().queue if isinstance(item, class_or_tuple)]
        return cls._classwide_stack().queue

    @classmethod
    def current(cls) -> Self | None:
        if cls._stack().qsize() == 0:
            return None
        return cls._stack().queue[-1]

    @classmethod
    def current_classwide(
        cls,
        class_or_tuple: type[ContextMixin] | tuple[type[ContextMixin], ...] | None = None,
    ) -> ContextMixin | None:
        queue = cls.classwide_stack_queue(class_or_tuple)
        if not queue:
            return None
        return queue[-1]

    def __enter__(self) -> Self:
        self._stack().put(self, block=False)
        self._classwide_stack().put(self, block=False)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._stack().get(block=False)
        self._classwide_stack().get(block=False)


def model_to_flat_dict(model_instance: BaseModel) -> dict[str, Any]:
    """Convert model to dict without recursive conversion."""
    model = model_instance.__class__
    result = {}
    for field_name in model.model_fields:
        result[field_name] = getattr(model_instance, field_name)
    return result

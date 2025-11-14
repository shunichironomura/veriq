from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from ._models import Verification


def assume[T, **P](verification: Verification[...]) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to mark that a calculation assumes a verification."""

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        # HACK: We should avoid modifying the function object directly,
        # but this is a simple way to attach metadata.
        # In the future, we might implement a builder class for calculations/verifications.
        if not hasattr(func, "__veriq_assumed_verifications__"):
            func.__veriq_assumed_verifications__ = []  # type: ignore[attr-defined]
        func.__veriq_assumed_verifications__.append(verification)  # type: ignore[attr-defined]
        return func

    return decorator

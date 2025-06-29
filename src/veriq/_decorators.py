from collections.abc import Callable

from ._models import Calculation, Verification


def calculation[T, **P](func: Callable[P, T]) -> Calculation:
    raise NotImplementedError


def verification[T, **P](func: Callable[P, T]) -> Verification:
    raise NotImplementedError

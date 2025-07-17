import inspect
from collections.abc import Callable

from ._models import Calculation, Verification, get_deps_from_signature, get_models_from_signature


def calculation[T, **P](func: Callable[P, T]) -> Calculation[T, P]:
    """Decorate a function to mark it as a calculation."""
    calc_deps = get_deps_from_signature(inspect.signature(func))
    model_deps = get_models_from_signature(inspect.signature(func))
    return Calculation(name=func.__name__, func=func, model_deps=model_deps, calc_deps=calc_deps)


def verification[**P](func: Callable[P, bool]) -> Verification[P]:
    """Decorate a function to mark it as a verification."""
    model_deps = get_models_from_signature(inspect.signature(func))
    calc_deps = get_deps_from_signature(inspect.signature(func))
    return Verification(name=func.__name__, func=func, model_deps=model_deps, calc_deps=calc_deps)

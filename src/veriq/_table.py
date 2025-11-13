from enum import StrEnum
from itertools import product
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


class Table[K: (StrEnum, tuple[StrEnum, ...]), V](dict[K, V]):
    """Exhaustive mapping from keys of type K to values of type V."""

    _key_type: type[K]
    _expected_keys: frozenset[K]

    @property
    def key_type(self) -> type[K]:
        """The type of the keys in the table."""
        return self._key_type

    @property
    def expected_keys(self) -> frozenset[K]:
        """The set of expected keys in the table."""
        return self._expected_keys

    def __init__(self, mapping_or_iterable: Mapping[K, V] | Iterable[tuple[K, V]], /, **kwargs: V) -> None:
        mapping = dict(mapping_or_iterable, **kwargs)

        if len(mapping) == 0:
            msg = "Table cannot be empty."
            raise ValueError(msg)

        # determine key types
        key_sample = next(iter(mapping.keys()))
        if isinstance(key_sample, tuple):
            key_types = tuple(type(k) for k in key_sample)
            for key_type in key_types:
                if not issubclass(key_type, StrEnum):
                    msg = f"Table key types must be StrEnum or tuple of StrEnum. Got: {key_types}"
                    raise TypeError(msg)
            expected_keys = frozenset(
                tuple(values)
                for values in product(
                    *(list(key_type) for key_type in key_types),
                )
            )
        else:
            key_type = type(key_sample)
            if not issubclass(key_type, StrEnum):
                msg = f"Table key type must be StrEnum or tuple of StrEnum. Got: {key_type}"
                raise TypeError(msg)
            expected_keys = frozenset(key_type)

        self._key_type = type(key_sample)
        self._expected_keys = expected_keys

        missing_keys = expected_keys - set(mapping.keys())
        if missing_keys:
            msg = f"Table is missing keys: {missing_keys}"
            raise ValueError(msg)

        disallowed_keys = set(mapping.keys()) - expected_keys
        if disallowed_keys:
            msg = f"Table has disallowed keys: {disallowed_keys}"
            raise ValueError(msg)

        super().__init__(mapping)

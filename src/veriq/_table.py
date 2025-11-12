from enum import StrEnum


class Table[K: (StrEnum, tuple[StrEnum, ...]), V](dict[K, V]):
    """Exhaustive mapping from keys of type K to values of type V."""

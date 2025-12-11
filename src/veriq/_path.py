import logging
from annotationlib import ForwardRef
from dataclasses import dataclass, field
from enum import StrEnum
from inspect import isclass
from itertools import product
from typing import TYPE_CHECKING, Any, ClassVar, Self, get_args, get_origin

from pydantic import BaseModel

from ._table import Table

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping

logger = logging.getLogger(__name__)


class PartBase:
    pass


@dataclass(slots=True, frozen=True)
class AttributePart(PartBase):
    name: str


@dataclass(slots=True, frozen=True)
class ItemPart(PartBase):
    key: str | tuple[str, ...]


@dataclass(slots=True, frozen=True)
class Path:
    root: str
    parts: tuple[PartBase, ...]

    def __str__(self) -> str:
        result = self.root
        for part in self.parts:
            match part:
                case AttributePart(name):
                    result += f".{name}"
                case ItemPart(key):
                    result += f"[{key}]"
                case _:
                    msg = f"Unknown part type: {type(part)}"
                    raise TypeError(msg)
        return result

    @classmethod
    def parse(cls, path_str: str) -> Self:
        s = path_str.strip()

        # Extract root by partitioning at the first occurrence of '.' or '['
        root_len = len(s)
        root = None
        for sep in (".", "["):
            root_candidate, sep_found, _parts_str_candidate = s.partition(sep)
            if sep_found and len(root_candidate) < root_len:
                root_len = len(root_candidate)
                root = root_candidate

        if root is None:
            return cls(root=s, parts=())

        s = s[root_len:]

        parts: list[PartBase] = []
        i = 0
        while i < len(s):
            if s[i] == ".":  # Attribute access
                i += 1
                start = i
                while i < len(s) and s[i] not in ".[":
                    i += 1
                name = s[start:i]
                parts.append(AttributePart(name=name))
            elif s[i] == "[":  # Item access
                i += 1
                start = i
                while i < len(s) and s[i] != "]":
                    i += 1
                key_str = s[start:i]
                if "," in key_str:
                    keys = tuple(k.strip() for k in key_str.split(","))
                    parts.append(ItemPart(key=keys))
                else:
                    parts.append(ItemPart(key=key_str.strip()))
                i += 1  # Skip the closing ']'
            else:
                msg = f"Unexpected character at position {i}: {s[i]}"
                raise ValueError(msg)

        return cls(root=root, parts=tuple(parts))


@dataclass(slots=True, frozen=True)
class ModelPath(Path):
    root: str
    parts: tuple[PartBase, ...]

    ROOT_SYMBOL: ClassVar[str] = "$"

    def __post_init__(self) -> None:
        if self.root != self.ROOT_SYMBOL:
            msg = f"ModelPath root must be '{self.ROOT_SYMBOL}'. Got: {self.root}"
            raise ValueError(msg)


@dataclass(slots=True, frozen=True)
class CalcPath(Path):
    root: str
    parts: tuple[PartBase, ...]

    PREFIX: ClassVar[str] = "@"

    def __post_init__(self) -> None:
        if not self.root.startswith(self.PREFIX):
            msg = f"CalcPath root must start with '{self.PREFIX}'. Got: {self.root}"
            raise ValueError(msg)

    @property
    def calc_name(self) -> str:
        return self.root[len(self.PREFIX) :]


@dataclass(slots=True, frozen=True)
class VerificationPath(Path):
    root: str
    parts: tuple[PartBase, ...] = field(default=())

    PREFIX: ClassVar[str] = "?"

    def __post_init__(self) -> None:
        if not self.root.startswith(self.PREFIX):
            msg = f"VerificationPath root must start with '{self.PREFIX}'. Got: {self.root}"
            raise ValueError(msg)
        if self.parts:
            msg = "VerificationPath must not have parts."
            raise ValueError(msg)

    @property
    def verification_name(self) -> str:
        return self.root[len(self.PREFIX) :]


def parse_path(path_str: str) -> ModelPath | CalcPath | VerificationPath:
    s = path_str.strip()
    if s.startswith(ModelPath.ROOT_SYMBOL):
        return ModelPath.parse(s)
    if s.startswith(CalcPath.PREFIX):
        return CalcPath.parse(s)
    if s.startswith(VerificationPath.PREFIX):
        return VerificationPath.parse(s)
    msg = f"Unknown path type for string: {path_str}"
    raise ValueError(msg)


@dataclass(slots=True, frozen=True)
class ProjectPath:
    scope: str
    path: ModelPath | CalcPath | VerificationPath

    def __str__(self) -> str:
        return f"{self.scope}::{self.path}"


def iter_leaf_path_parts(  # noqa: PLR0912, C901
    model: Any,
    *,
    _current_path_parts: tuple[PartBase, ...] = (),
) -> Generator[tuple[PartBase, ...]]:
    if isinstance(model, ForwardRef):
        model = model.evaluate()

    # Handle generic aliases (e.g., Table[Option, float])
    origin = get_origin(model)
    if (origin is not None and origin is Table) or (isclass(origin) and issubclass(origin, Table)):
        # Yield the whole table first
        yield _current_path_parts

        # Extract type arguments from the generic Table
        type_args = get_args(model)
        if len(type_args) == 2:
            key_type_arg, _value_type_arg = type_args

            # Determine the actual enum type(s)
            key_type_args = get_args(key_type_arg)
            enum_types = key_type_args if key_type_args else (key_type_arg,)

            # Generate expected keys based on enum types
            if len(enum_types) == 1:
                # Single StrEnum key
                enum_type = enum_types[0]
                if isclass(enum_type) and issubclass(enum_type, StrEnum):
                    for enum_value in enum_type:
                        yield (
                            *_current_path_parts,
                            ItemPart(key=enum_value.value),
                        )
            # Tuple of StrEnum keys
            elif all(isclass(et) and issubclass(et, StrEnum) for et in enum_types):
                for values in product(*(list(et) for et in enum_types)):
                    key = ",".join(v.value for v in values)
                    yield (
                        *_current_path_parts,
                        ItemPart(key=key),
                    )
        return

    if not isclass(model):
        yield _current_path_parts
        return
    if issubclass(model, Table):
        # This branch handles non-generic Table classes (shouldn't normally happen)
        # For a properly parameterized Table, we handle it above
        yield _current_path_parts
        return
    if not issubclass(model, BaseModel):
        yield _current_path_parts
        return

    for field_name, field_info in model.model_fields.items():
        field_type = field_info.annotation
        if isinstance(field_type, ForwardRef):
            field_type = field_type.evaluate()
        if field_type is None:
            continue
        yield from iter_leaf_path_parts(
            field_type,
            _current_path_parts=(*_current_path_parts, AttributePart(name=field_name)),
        )


def get_value_by_parts(data: BaseModel, parts: tuple[PartBase, ...]) -> Any:
    current: Any = data
    for part in parts:
        match part:
            case AttributePart(name):
                current = getattr(current, name)
            case ItemPart(key):
                # If accessing a Table, convert string key(s) to enum(s)
                if isinstance(current, Table):
                    key_type = current.key_type
                    # Check if the key type is tuple (for multi-enum keys)
                    if key_type is tuple:
                        # Tuple key - get the enum types from the key sample
                        key_sample = next(iter(current.keys()))
                        enum_types = tuple(type(k) for k in key_sample)
                        # Parse the string key
                        parts_str = key if isinstance(key, tuple) else key.split(",")
                        # Convert to enum tuple
                        key = tuple(enum_type(part) for enum_type, part in zip(enum_types, parts_str, strict=True))
                    else:
                        # Single enum key
                        key = key_type(key)
                current = current[key]
            case _:
                msg = f"Unknown part type: {type(part)}"
                raise TypeError(msg)
    return current


def hydrate_value_by_leaf_values[T](model: type[T], leaf_values: Mapping[tuple[PartBase, ...], Any]) -> T:  # noqa: PLR0912, C901, PLR0915
    # If there's a value at the empty path (), it represents the complete object
    # This happens when we store both the whole Table and individual items
    if () in leaf_values:
        return leaf_values[()]  # type: ignore[no-any-return]

    # Handle generic Table types (e.g., Table[Option, float])
    origin = get_origin(model)
    if origin is not None and (origin is Table or (isclass(origin) and issubclass(origin, Table))):
        # Extract type arguments to get the key type
        type_args = get_args(model)
        if len(type_args) == 2:
            key_type_arg, _value_type_arg = type_args

            # Determine the actual enum type(s)
            key_type_args = get_args(key_type_arg)
            enum_types = key_type_args if key_type_args else (key_type_arg,)

            table_mapping = {}
            for parts, value in leaf_values.items():
                key_part = parts[0]
                if not isinstance(key_part, ItemPart):
                    msg = f"Expected ItemPart for Table key, got: {type(key_part)}"
                    raise TypeError(msg)
                str_key = key_part.key

                # Deserialize the key based on whether it's a tuple or single enum
                if len(enum_types) == 1:
                    # Single StrEnum key
                    enum_type = enum_types[0]
                    key = enum_type(str_key)
                else:
                    # Tuple of StrEnum keys
                    parts_str = str_key.split(",") if isinstance(str_key, str) else str_key
                    if isinstance(parts_str, str):
                        parts_str = [parts_str]
                    key = tuple(enum_type(part) for enum_type, part in zip(enum_types, parts_str, strict=True))

                table_mapping[key] = value
            return origin(table_mapping)  # type: ignore[no-any-return]
        msg = f"Table type must have exactly 2 type arguments, got {len(type_args)}"
        raise TypeError(msg)

    if isclass(model) and issubclass(model, Table):
        table_mapping = {}
        for parts, value in leaf_values.items():
            key_part = parts[0]
            if not isinstance(key_part, ItemPart):
                msg = f"Expected ItemPart for Table key, got: {type(key_part)}"
                raise TypeError(msg)
            key = key_part.key
            table_mapping[key] = value
        return model(table_mapping)

    if not isclass(model) or not issubclass(model, BaseModel):
        if len(leaf_values) != 1 or any(len(parts) != 0 for parts in leaf_values):
            msg = f"Expected single leaf value for non-model type '{model}', got: {leaf_values}"
            raise ValueError(msg)
        return next(iter(leaf_values.values()))  # type: ignore[no-any-return]

    field_values: dict[str, Any] = {}

    for field_name, field_info in model.model_fields.items():
        field_type = field_info.annotation
        if isinstance(field_type, ForwardRef):
            field_type = field_type.evaluate()
        if field_type is None:
            continue

        matching_leaf_parts = [
            parts
            for parts in leaf_values
            if len(parts) > 0 and isinstance(parts[0], AttributePart) and parts[0].name == field_name
        ]
        logger.debug(f"Hydrating field '{field_name}' of type '{field_type}' with leaf parts: {matching_leaf_parts}")
        logger.debug(f"Available leaf values: {leaf_values}")

        field_value: Any
        if issubclass(field_type, BaseModel):
            sub_leaf_values = {tuple(parts[1:]): leaf_values[parts] for parts in matching_leaf_parts}
            field_value = hydrate_value_by_leaf_values(field_type, sub_leaf_values)
        elif issubclass(field_type, Table):
            table_mapping = {}
            for parts in matching_leaf_parts:
                key_part = parts[1]
                if not isinstance(key_part, ItemPart):
                    msg = f"Expected ItemPart for Table key, got: {type(key_part)}"
                    raise TypeError(msg)
                key = key_part.key
                value = leaf_values[parts]
                table_mapping[key] = value
            field_value = field_type(table_mapping)
        else:
            if len(matching_leaf_parts) != 1 or len(matching_leaf_parts[0]) != 1:
                msg = f"Expected single leaf part for field '{field_name}', got: {matching_leaf_parts}"
                raise ValueError(msg)
            field_value = leaf_values[matching_leaf_parts[0]]

        field_values[field_name] = field_value

    return model(**field_values)

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, ClassVar, Self

from pydantic import BaseModel


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


def fetch(root_model: Any, path: str) -> Any:
    path_obj = ModelPath.parse(path)
    current: Any = root_model
    for part in path_obj.parts:
        match part:
            case AttributePart(name):
                current = getattr(current, name)
            case ItemPart(key):
                current = current[key]
            case _:
                msg = f"Unknown part type: {type(part)}"
                raise TypeError(msg)

    return current


@dataclass(slots=True, frozen=True)
class ProjectPath:
    scope: str
    path: ModelPath | CalcPath | VerificationPath

    def __str__(self) -> str:
        return f"{self.scope}::{self.path}"


if __name__ == "__main__":
    import veriq as vq

    scope = vq.Scope("scope_name")

    class Option(StrEnum):
        OPTION_A = "option_a"
        OPTION_B = "option_b"

    class Mode(StrEnum):
        NOMINAL = "nominal"
        SAFE = "safe"

    # For debugging
    vq.Table = dict

    @scope.root_model()
    class RootModel(BaseModel):
        x: int  # "x"
        sub: SubModel  # "sub"
        table: vq.Table[Option, float]  # "table"
        table_2: vq.Table[tuple[Mode, Option], float]  # "table_2"

    class SubModel(BaseModel):
        a: int
        b: int

    @scope.calculation()
    def calc_42() -> int:  # "calc_42"
        return 42

    class CalcResult(BaseModel):
        y: int

    @scope.calculation()
    def calc_y() -> CalcResult:
        return CalcResult(y=100)

    model = RootModel(
        x=10,
        sub=SubModel(a=1, b=2),
        table=vq.Table(
            {
                Option.OPTION_A: 3.14,
                Option.OPTION_B: 2.71,
            },
        ),
        table_2=vq.Table(
            {
                (Mode.NOMINAL, Option.OPTION_A): 1.0,
                (Mode.NOMINAL, Option.OPTION_B): 0.8,
                (Mode.SAFE, Option.OPTION_A): 0.5,
                (Mode.SAFE, Option.OPTION_B): 0.4,
            },
        ),
    )

    path = ModelPath(
        "$",
        (
            AttributePart(name="sub"),
            AttributePart(name="a"),
        ),
    )
    assert str(path) == "$.sub.a"

    assert ModelPath.parse("$.sub.a") == path

    assert fetch(model, "$.x") == 10
    assert fetch(model, "$.sub.a") == 1
    assert fetch(model, "$.sub.b") == 2
    assert fetch(model, "$.table[option_a]") == 3.14
    assert fetch(model, "$.table_2[nominal, option_b]") == 0.8

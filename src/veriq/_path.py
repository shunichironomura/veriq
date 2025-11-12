from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel

import veriq as vq


class PartBase:
    pass


@dataclass(slots=True, frozen=True)
class AttributePart(PartBase):
    name: str


@dataclass(slots=True, frozen=True)
class ItemPart(PartBase):
    key: str | tuple[str, ...]


@dataclass(slots=True, frozen=True)
class ModelPath:
    parts: list[PartBase]

    def __str__(self) -> str:
        result = "$"
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
        if not s.startswith("$"):
            msg = "Path must start with '$'"
            raise ValueError(msg)

        parts: list[PartBase] = []
        i = 1  # Skip the initial '$'
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

        return cls(parts=parts)


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


# def calc(root_model: BaseModel, calc_name: str, path: str) -> Any:
#     raise NotImplementedError


if __name__ == "__main__":
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
        [
            AttributePart(name="sub"),
            AttributePart(name="a"),
        ],
    )
    assert str(path) == "$.sub.a"

    assert ModelPath.parse("$.sub.a") == path

    assert fetch(model, "$.x") == 10
    assert fetch(model, "$.sub.a") == 1
    assert fetch(model, "$.sub.b") == 2
    assert fetch(model, "$.table[option_a]") == 3.14
    assert fetch(model, "$.table_2[nominal, option_b]") == 0.8

    # assert calc(model, "calc_42", "$") == 42

    # assert calc(model, "calc_y", "y") == 100
    # assert calc(model, "calc_y", "$.y") == 100

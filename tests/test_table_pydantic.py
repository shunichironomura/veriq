"""Tests for Pydantic integration with vq.Table."""

from enum import StrEnum

import pydantic
import pytest

import veriq as vq


class Option(StrEnum):
    OPTION_A = "option_a"
    OPTION_B = "option_b"


class Mode(StrEnum):
    NOMINAL = "nominal"
    SAFE = "safe"


def test_table_in_pydantic_model_single_key() -> None:
    """Test that vq.Table can be used as a field in a Pydantic model with a single StrEnum key."""

    class Model(pydantic.BaseModel):
        table: vq.Table[Option, float]

    # Create a valid table
    table = vq.Table(
        {
            Option.OPTION_A: 3.14,
            Option.OPTION_B: 2.71,
        },
    )

    # Test that the model accepts the table
    model = Model(table=table)
    assert model.table == table
    assert model.table[Option.OPTION_A] == 3.14
    assert model.table[Option.OPTION_B] == 2.71


def test_table_in_pydantic_model_tuple_key() -> None:
    """Test that vq.Table can be used as a field in a Pydantic model with a tuple of StrEnum keys."""

    class Model(pydantic.BaseModel):
        table: vq.Table[tuple[Mode, Option], float]

    # Create a valid table
    table = vq.Table(
        {
            (Mode.NOMINAL, Option.OPTION_A): 1.0,
            (Mode.NOMINAL, Option.OPTION_B): 0.8,
            (Mode.SAFE, Option.OPTION_A): 0.5,
            (Mode.SAFE, Option.OPTION_B): 0.4,
        },
    )

    # Test that the model accepts the table
    model = Model(table=table)
    assert model.table == table
    assert model.table[(Mode.NOMINAL, Option.OPTION_A)] == 1.0
    assert model.table[(Mode.NOMINAL, Option.OPTION_B)] == 0.8
    assert model.table[(Mode.SAFE, Option.OPTION_A)] == 0.5
    assert model.table[(Mode.SAFE, Option.OPTION_B)] == 0.4


def test_table_serialization_single_key() -> None:
    """Test that vq.Table with single StrEnum key serializes correctly."""

    class Model(pydantic.BaseModel):
        table: vq.Table[Option, float]

    table = vq.Table(
        {
            Option.OPTION_A: 3.14,
            Option.OPTION_B: 2.71,
        },
    )

    model = Model(table=table)
    serialized = model.model_dump()

    expected = {
        "table": {
            "option_a": 3.14,
            "option_b": 2.71,
        },
    }

    assert serialized == expected


def test_table_serialization_tuple_key() -> None:
    """Test that vq.Table with tuple of StrEnum keys serializes correctly."""

    class Model(pydantic.BaseModel):
        table: vq.Table[tuple[Mode, Option], float]

    table = vq.Table(
        {
            (Mode.NOMINAL, Option.OPTION_A): 1.0,
            (Mode.NOMINAL, Option.OPTION_B): 0.8,
            (Mode.SAFE, Option.OPTION_A): 0.5,
            (Mode.SAFE, Option.OPTION_B): 0.4,
        },
    )

    model = Model(table=table)
    serialized = model.model_dump()

    expected = {
        "table": {
            "nominal,option_a": 1.0,
            "nominal,option_b": 0.8,
            "safe,option_a": 0.5,
            "safe,option_b": 0.4,
        },
    }

    assert serialized == expected


def test_table_deserialization_single_key() -> None:
    """Test that vq.Table with single StrEnum key can be deserialized from dict."""

    class Model(pydantic.BaseModel):
        table: vq.Table[Option, float]

    data = {
        "table": {
            "option_a": 3.14,
            "option_b": 2.71,
        },
    }

    model = Model(**data)
    assert model.table[Option.OPTION_A] == 3.14
    assert model.table[Option.OPTION_B] == 2.71


def test_table_deserialization_tuple_key() -> None:
    """Test that vq.Table with tuple of StrEnum keys can be deserialized from dict."""

    class Model(pydantic.BaseModel):
        table: vq.Table[tuple[Mode, Option], float]

    data = {
        "table": {
            "nominal,option_a": 1.0,
            "nominal,option_b": 0.8,
            "safe,option_a": 0.5,
            "safe,option_b": 0.4,
        },
    }

    model = Model(**data)
    assert model.table[(Mode.NOMINAL, Option.OPTION_A)] == 1.0
    assert model.table[(Mode.NOMINAL, Option.OPTION_B)] == 0.8
    assert model.table[(Mode.SAFE, Option.OPTION_A)] == 0.5
    assert model.table[(Mode.SAFE, Option.OPTION_B)] == 0.4


def test_table_validation_missing_keys() -> None:
    """Test that deserialization fails when keys are missing."""

    class Model(pydantic.BaseModel):
        table: vq.Table[Option, float]

    data = {
        "table": {
            "option_a": 3.14,
            # Missing option_b
        },
    }

    with pytest.raises(pydantic.ValidationError):
        Model(**data)


def test_table_validation_extra_keys() -> None:
    """Test that deserialization fails when extra keys are present."""

    class Model(pydantic.BaseModel):
        table: vq.Table[Option, float]

    data = {
        "table": {
            "option_a": 3.14,
            "option_b": 2.71,
            "option_c": 1.41,  # Extra key
        },
    }

    with pytest.raises(pydantic.ValidationError):
        Model(**data)


def test_table_roundtrip_single_key() -> None:
    """Test that serialization and deserialization are inverse operations for single key."""

    class Model(pydantic.BaseModel):
        table: vq.Table[Option, float]

    original_table = vq.Table(
        {
            Option.OPTION_A: 3.14,
            Option.OPTION_B: 2.71,
        },
    )

    model = Model(table=original_table)
    serialized = model.model_dump()
    deserialized_model = Model(**serialized)

    assert deserialized_model.table == original_table


def test_table_roundtrip_tuple_key() -> None:
    """Test that serialization and deserialization are inverse operations for tuple key."""

    class Model(pydantic.BaseModel):
        table: vq.Table[tuple[Mode, Option], float]

    original_table = vq.Table(
        {
            (Mode.NOMINAL, Option.OPTION_A): 1.0,
            (Mode.NOMINAL, Option.OPTION_B): 0.8,
            (Mode.SAFE, Option.OPTION_A): 0.5,
            (Mode.SAFE, Option.OPTION_B): 0.4,
        },
    )

    model = Model(table=original_table)
    serialized = model.model_dump()
    deserialized_model = Model(**serialized)

    assert deserialized_model.table == original_table

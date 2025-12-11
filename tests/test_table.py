from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel

import veriq as vq
from veriq._eval import evaluate_project
from veriq._path import CalcPath, ProjectPath


class Option(StrEnum):
    OPTION_A = "option_a"
    OPTION_B = "option_b"


class Region(StrEnum):
    NORTH = "north"
    SOUTH = "south"


class Product(StrEnum):
    WIDGET = "widget"
    GADGET = "gadget"


def test_table_as_calc_output() -> None:
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    @scope.root_model()
    class RootModel(BaseModel):
        input_table: vq.Table[Option, float]

    @scope.calculation()
    def output_table(
        input_table: Annotated[vq.Table[Option, float], vq.Ref("$.input_table")],
    ) -> vq.Table[Option, float]:
        # Transform the input table by multiplying by 2
        return vq.Table(
            {
                Option.OPTION_A: input_table[Option.OPTION_A] * 2,
                Option.OPTION_B: input_table[Option.OPTION_B] * 2,
            },
        )

    # Create model data
    model_data = {
        scope.name: RootModel(
            input_table=vq.Table(
                {
                    Option.OPTION_A: 3.14,
                    Option.OPTION_B: 2.71,
                },
            ),
        ),
    }

    # Evaluate the project
    result = evaluate_project(project, model_data)

    # Check that the calculation was evaluated correctly
    # Get the whole Table output
    calc_output = result[
        ProjectPath(
            scope="Test Scope",
            path=CalcPath(root="@output_table", parts=()),
        )
    ]

    assert isinstance(calc_output, vq.Table)
    assert calc_output[Option.OPTION_A] == 6.28
    assert calc_output[Option.OPTION_B] == 5.42


def test_table_as_calc_output_with_calc_input() -> None:
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    @scope.root_model()
    class RootModel(BaseModel):
        input_table: vq.Table[Option, float]

    @scope.calculation()
    def double_table(
        input_table: Annotated[vq.Table[Option, float], vq.Ref("$.input_table")],
    ) -> vq.Table[Option, float]:
        # Transform the input table by multiplying by 2
        return vq.Table(
            {
                Option.OPTION_A: input_table[Option.OPTION_A] * 2,
                Option.OPTION_B: input_table[Option.OPTION_B] * 2,
            },
        )

    @scope.calculation()
    def output_table(
        doubled_table: Annotated[vq.Table[Option, float], vq.Ref("@double_table")],
    ) -> vq.Table[Option, float]:
        # Further transform the doubled table by multiplying by 3
        return vq.Table(
            {
                Option.OPTION_A: doubled_table[Option.OPTION_A] * 3,
                Option.OPTION_B: doubled_table[Option.OPTION_B] * 3,
            },
        )

    # Create model data
    model_data = {
        "Test Scope": RootModel(
            input_table=vq.Table(
                {
                    Option.OPTION_A: 3.14,
                    Option.OPTION_B: 2.71,
                },
            ),
        ),
    }

    # Evaluate the project
    result = evaluate_project(project, model_data)

    # Check that the calculation was evaluated correctly
    # Get the whole Table output
    calc_output = result[
        ProjectPath(
            scope="Test Scope",
            path=CalcPath(root="@output_table", parts=()),
        )
    ]

    assert isinstance(calc_output, vq.Table)
    assert calc_output[Option.OPTION_A] == 3.14 * 2 * 3
    assert calc_output[Option.OPTION_B] == 2.71 * 2 * 3


def test_table_with_tuple_index_as_calc_output() -> None:
    """Test table with tuple of StrEnums as index."""
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    @scope.root_model()
    class RootModel(BaseModel):
        input_table: vq.Table[tuple[Region, Product], float]

    @scope.calculation()
    def output_table(
        input_table: Annotated[vq.Table[tuple[Region, Product], float], vq.Ref("$.input_table")],
    ) -> vq.Table[tuple[Region, Product], float]:
        # Transform the input table by multiplying by 2
        return vq.Table(
            {
                (Region.NORTH, Product.WIDGET): input_table[(Region.NORTH, Product.WIDGET)] * 2,
                (Region.NORTH, Product.GADGET): input_table[(Region.NORTH, Product.GADGET)] * 2,
                (Region.SOUTH, Product.WIDGET): input_table[(Region.SOUTH, Product.WIDGET)] * 2,
                (Region.SOUTH, Product.GADGET): input_table[(Region.SOUTH, Product.GADGET)] * 2,
            },
        )

    # Create model data
    model_data = {
        scope.name: RootModel(
            input_table=vq.Table(
                {
                    (Region.NORTH, Product.WIDGET): 10.0,
                    (Region.NORTH, Product.GADGET): 20.0,
                    (Region.SOUTH, Product.WIDGET): 30.0,
                    (Region.SOUTH, Product.GADGET): 40.0,
                },
            ),
        ),
    }

    # Evaluate the project
    result = evaluate_project(project, model_data)

    # Check that the calculation was evaluated correctly
    # Get the whole Table output
    calc_output = result[
        ProjectPath(
            scope="Test Scope",
            path=CalcPath(root="@output_table", parts=()),
        )
    ]

    assert isinstance(calc_output, vq.Table)
    assert calc_output[(Region.NORTH, Product.WIDGET)] == 20.0
    assert calc_output[(Region.NORTH, Product.GADGET)] == 40.0
    assert calc_output[(Region.SOUTH, Product.WIDGET)] == 60.0
    assert calc_output[(Region.SOUTH, Product.GADGET)] == 80.0


def test_table_with_tuple_index_as_calc_output_with_calc_input() -> None:
    """Test table with tuple of StrEnums as index with chained calculations."""
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    @scope.root_model()
    class RootModel(BaseModel):
        input_table: vq.Table[tuple[Region, Product], float]

    @scope.calculation()
    def double_table(
        input_table: Annotated[vq.Table[tuple[Region, Product], float], vq.Ref("$.input_table")],
    ) -> vq.Table[tuple[Region, Product], float]:
        # Transform the input table by multiplying by 2
        return vq.Table(
            {
                (Region.NORTH, Product.WIDGET): input_table[(Region.NORTH, Product.WIDGET)] * 2,
                (Region.NORTH, Product.GADGET): input_table[(Region.NORTH, Product.GADGET)] * 2,
                (Region.SOUTH, Product.WIDGET): input_table[(Region.SOUTH, Product.WIDGET)] * 2,
                (Region.SOUTH, Product.GADGET): input_table[(Region.SOUTH, Product.GADGET)] * 2,
            },
        )

    @scope.calculation()
    def output_table(
        doubled_table: Annotated[vq.Table[tuple[Region, Product], float], vq.Ref("@double_table")],
    ) -> vq.Table[tuple[Region, Product], float]:
        # Further transform the doubled table by multiplying by 3
        return vq.Table(
            {
                (Region.NORTH, Product.WIDGET): doubled_table[(Region.NORTH, Product.WIDGET)] * 3,
                (Region.NORTH, Product.GADGET): doubled_table[(Region.NORTH, Product.GADGET)] * 3,
                (Region.SOUTH, Product.WIDGET): doubled_table[(Region.SOUTH, Product.WIDGET)] * 3,
                (Region.SOUTH, Product.GADGET): doubled_table[(Region.SOUTH, Product.GADGET)] * 3,
            },
        )

    # Create model data
    model_data = {
        "Test Scope": RootModel(
            input_table=vq.Table(
                {
                    (Region.NORTH, Product.WIDGET): 10.0,
                    (Region.NORTH, Product.GADGET): 20.0,
                    (Region.SOUTH, Product.WIDGET): 30.0,
                    (Region.SOUTH, Product.GADGET): 40.0,
                },
            ),
        ),
    }

    # Evaluate the project
    result = evaluate_project(project, model_data)

    # Check that the calculation was evaluated correctly
    # Get the whole Table output
    calc_output = result[
        ProjectPath(
            scope="Test Scope",
            path=CalcPath(root="@output_table", parts=()),
        )
    ]

    assert isinstance(calc_output, vq.Table)
    assert calc_output[(Region.NORTH, Product.WIDGET)] == 10.0 * 2 * 3
    assert calc_output[(Region.NORTH, Product.GADGET)] == 20.0 * 2 * 3
    assert calc_output[(Region.SOUTH, Product.WIDGET)] == 30.0 * 2 * 3
    assert calc_output[(Region.SOUTH, Product.GADGET)] == 40.0 * 2 * 3


def test_table_with_triple_tuple_index() -> None:
    """Test table with tuple of 3 StrEnums as index."""
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    @scope.root_model()
    class RootModel(BaseModel):
        input_table: vq.Table[tuple[Region, Product, Option], float]

    @scope.calculation()
    def output_table(
        input_table: Annotated[vq.Table[tuple[Region, Product, Option], float], vq.Ref("$.input_table")],
    ) -> vq.Table[tuple[Region, Product, Option], float]:
        # Transform the input table by adding 100
        return vq.Table(
            {
                (Region.NORTH, Product.WIDGET, Option.OPTION_A): input_table[(Region.NORTH, Product.WIDGET, Option.OPTION_A)] + 100,
                (Region.NORTH, Product.WIDGET, Option.OPTION_B): input_table[(Region.NORTH, Product.WIDGET, Option.OPTION_B)] + 100,
                (Region.NORTH, Product.GADGET, Option.OPTION_A): input_table[(Region.NORTH, Product.GADGET, Option.OPTION_A)] + 100,
                (Region.NORTH, Product.GADGET, Option.OPTION_B): input_table[(Region.NORTH, Product.GADGET, Option.OPTION_B)] + 100,
                (Region.SOUTH, Product.WIDGET, Option.OPTION_A): input_table[(Region.SOUTH, Product.WIDGET, Option.OPTION_A)] + 100,
                (Region.SOUTH, Product.WIDGET, Option.OPTION_B): input_table[(Region.SOUTH, Product.WIDGET, Option.OPTION_B)] + 100,
                (Region.SOUTH, Product.GADGET, Option.OPTION_A): input_table[(Region.SOUTH, Product.GADGET, Option.OPTION_A)] + 100,
                (Region.SOUTH, Product.GADGET, Option.OPTION_B): input_table[(Region.SOUTH, Product.GADGET, Option.OPTION_B)] + 100,
            },
        )

    # Create model data
    model_data = {
        scope.name: RootModel(
            input_table=vq.Table(
                {
                    (Region.NORTH, Product.WIDGET, Option.OPTION_A): 1.0,
                    (Region.NORTH, Product.WIDGET, Option.OPTION_B): 2.0,
                    (Region.NORTH, Product.GADGET, Option.OPTION_A): 3.0,
                    (Region.NORTH, Product.GADGET, Option.OPTION_B): 4.0,
                    (Region.SOUTH, Product.WIDGET, Option.OPTION_A): 5.0,
                    (Region.SOUTH, Product.WIDGET, Option.OPTION_B): 6.0,
                    (Region.SOUTH, Product.GADGET, Option.OPTION_A): 7.0,
                    (Region.SOUTH, Product.GADGET, Option.OPTION_B): 8.0,
                },
            ),
        ),
    }

    # Evaluate the project
    result = evaluate_project(project, model_data)

    # Check that the calculation was evaluated correctly
    calc_output = result[
        ProjectPath(
            scope="Test Scope",
            path=CalcPath(root="@output_table", parts=()),
        )
    ]

    assert isinstance(calc_output, vq.Table)
    assert calc_output[(Region.NORTH, Product.WIDGET, Option.OPTION_A)] == 101.0
    assert calc_output[(Region.NORTH, Product.WIDGET, Option.OPTION_B)] == 102.0
    assert calc_output[(Region.NORTH, Product.GADGET, Option.OPTION_A)] == 103.0
    assert calc_output[(Region.NORTH, Product.GADGET, Option.OPTION_B)] == 104.0
    assert calc_output[(Region.SOUTH, Product.WIDGET, Option.OPTION_A)] == 105.0
    assert calc_output[(Region.SOUTH, Product.WIDGET, Option.OPTION_B)] == 106.0
    assert calc_output[(Region.SOUTH, Product.GADGET, Option.OPTION_A)] == 107.0
    assert calc_output[(Region.SOUTH, Product.GADGET, Option.OPTION_B)] == 108.0

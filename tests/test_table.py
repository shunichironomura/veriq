from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel

import veriq as vq
from veriq._eval import evaluate_project
from veriq._path import CalcPath, ProjectPath


class Option(StrEnum):
    OPTION_A = "option_a"
    OPTION_B = "option_b"


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
    assert calc_output[Option.OPTION_A] == 6.28
    assert calc_output[Option.OPTION_B] == 5.42

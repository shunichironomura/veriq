from enum import StrEnum

from pydantic import BaseModel

import veriq as vq


class Option(StrEnum):
    OPTION_A = "option_a"
    OPTION_B = "option_b"


def test_table_as_calc_output() -> None:
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    @scope.root_model()
    class RootModel(BaseModel):
        table: vq.Table[Option, float]

    @scope.calculation()
    def output_table() -> vq.Table[Option, float]:
        return vq.Table(
            {
                Option.OPTION_A: 6.28,
                Option.OPTION_B: 5.42,
            },
        )

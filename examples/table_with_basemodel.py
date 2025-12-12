"""Example demonstrating Table with BaseModel values."""

from enum import StrEnum, unique
from typing import Annotated

from pydantic import BaseModel

import veriq as vq


# Define operation modes
@unique
class OperationMode(StrEnum):
    NOMINAL = "nominal"
    SAFE = "safe"
    MISSION = "mission"


# Define a component configuration (BaseModel)
class PowerConfig(BaseModel):
    """Power configuration for an operation mode."""

    consumption: float  # in Watts
    max_peak: float  # in Watts
    voltage: float  # in Volts


# Create project and scope
project = vq.Project("SatelliteExample")
power = vq.Scope("Power")
project.add_scope(power)


# Define the root model with a Table of BaseModel values
@power.root_model()
class PowerModel(BaseModel):
    """Power subsystem model."""

    battery_capacity: float  # in Watt-hours
    # Table mapping operation modes to their power configurations
    mode_configs: vq.Table[OperationMode, PowerConfig]


# Add a simple calculation
class PowerResult(BaseModel):
    """Results from power calculations."""

    max_discharge_power: float  # in Watts


@power.calculation()
def calculate_battery_performance(
    battery_capacity: Annotated[float, vq.Ref("$.battery_capacity")],
) -> PowerResult:
    """Calculate maximum discharge power from battery."""
    max_discharge = battery_capacity * 0.5  # 0.5C discharge rate
    return PowerResult(max_discharge_power=max_discharge)


# Example usage:
if __name__ == "__main__":
    from pathlib import Path

    # Define input data
    input_data_dict = {
        "battery_capacity": 1000.0,
        "mode_configs": {
            "nominal": {
                "consumption": 100.0,
                "max_peak": 200.0,
                "voltage": 12.0,
            },
            "safe": {
                "consumption": 20.0,
                "max_peak": 50.0,
                "voltage": 12.0,
            },
            "mission": {
                "consumption": 150.0,
                "max_peak": 300.0,
                "voltage": 12.0,
            },
        },
    }

    # Validate and create model instance
    model = PowerModel.model_validate(input_data_dict)
    model_data = {"Power": model}

    # Evaluate project
    results = vq.evaluate_project(project, model_data)

    # Export to TOML
    output_path = Path("output.toml")
    vq.export_to_toml(project, model_data, results, output_path)
    print(f"✓ Exported results to {output_path}")

    # Load back and verify
    loaded_data = vq.load_model_data_from_toml(project, output_path)
    print(f"✓ Loaded data back from {output_path}")

    # Verify the data
    assert loaded_data["Power"].battery_capacity == 1000.0
    assert loaded_data["Power"].mode_configs[OperationMode.NOMINAL].consumption == 100.0
    print("✓ Data roundtrip successful!")

    # Clean up
    output_path.unlink()
    print(f"✓ Cleaned up {output_path}")

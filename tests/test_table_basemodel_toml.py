"""Test that Table with BaseModel values can be exported to TOML."""

import tomllib
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel

import veriq as vq

if TYPE_CHECKING:
    from pathlib import Path


class OperationMode(StrEnum):
    NOMINAL = "nominal"
    SAFE = "safe"


class ComponentConfig(BaseModel):
    """Configuration for a component in a specific operation mode."""

    power_consumption: float
    temperature_limit: float


class ComponentDesign(BaseModel):
    """Design parameters for a component with mode-specific configs."""

    name: str
    configs: vq.Table[OperationMode, ComponentConfig]


def test_table_with_basemodel_values_export_to_toml(tmp_path: Path) -> None:
    """Test that a Table with BaseModel values can be exported to TOML."""
    # Create a project
    project = vq.Project("TestProject")
    component_scope = vq.Scope("Component")
    project.add_scope(component_scope)

    # Define the root model
    @component_scope.root_model()
    class ComponentModel(BaseModel):
        design: ComponentDesign

    # Create input data with a Table of BaseModel values
    input_data = {
        "Component": ComponentModel(
            design=ComponentDesign(
                name="TestComponent",
                configs=vq.Table(
                    {
                        OperationMode.NOMINAL: ComponentConfig(
                            power_consumption=100.0,
                            temperature_limit=85.0,
                        ),
                        OperationMode.SAFE: ComponentConfig(
                            power_consumption=20.0,
                            temperature_limit=70.0,
                        ),
                    },
                ),
            ),
        ),
    }

    # Evaluate the project (this will populate results with the model data)
    results = vq.evaluate_project(project, input_data)

    # Export to TOML - this should now work with the fix
    output_path = tmp_path / "output.toml"
    vq.export_to_toml(project, input_data, results, output_path)

    # Verify the file was created
    assert output_path.exists()


def test_table_with_basemodel_values_roundtrip(tmp_path: Path) -> None:
    """Test that a Table with BaseModel values can be exported and re-imported."""
    # Create a project
    project = vq.Project("TestProject")
    component_scope = vq.Scope("Component")
    project.add_scope(component_scope)

    # Define the root model
    @component_scope.root_model()
    class ComponentModel(BaseModel):
        design: ComponentDesign

    # Create input data
    original_data = {
        "Component": ComponentModel(
            design=ComponentDesign(
                name="TestComponent",
                configs=vq.Table(
                    {
                        OperationMode.NOMINAL: ComponentConfig(
                            power_consumption=100.0,
                            temperature_limit=85.0,
                        ),
                        OperationMode.SAFE: ComponentConfig(
                            power_consumption=20.0,
                            temperature_limit=70.0,
                        ),
                    },
                ),
            ),
        ),
    }

    # Evaluate
    results = vq.evaluate_project(project, original_data)

    # Export to TOML
    output_path = tmp_path / "output.toml"
    vq.export_to_toml(project, original_data, results, output_path)

    # Verify the file was created
    assert output_path.exists()

    # Load the data back
    loaded_data = vq.load_model_data_from_toml(project, output_path)

    # Verify the loaded data matches the original
    assert loaded_data["Component"].design.name == "TestComponent"
    assert loaded_data["Component"].design.configs[OperationMode.NOMINAL].power_consumption == 100.0
    assert loaded_data["Component"].design.configs[OperationMode.NOMINAL].temperature_limit == 85.0
    assert loaded_data["Component"].design.configs[OperationMode.SAFE].power_consumption == 20.0
    assert loaded_data["Component"].design.configs[OperationMode.SAFE].temperature_limit == 70.0


def test_table_with_basemodel_values_toml_structure(tmp_path: Path) -> None:
    """Test that the TOML file structure is correct for Table with BaseModel values."""

    # Create a project
    project = vq.Project("TestProject")
    component_scope = vq.Scope("Component")
    project.add_scope(component_scope)

    # Define the root model
    @component_scope.root_model()
    class ComponentModel(BaseModel):
        design: ComponentDesign

    # Create input data
    input_data = {
        "Component": ComponentModel(
            design=ComponentDesign(
                name="TestComponent",
                configs=vq.Table(
                    {
                        OperationMode.NOMINAL: ComponentConfig(
                            power_consumption=100.0,
                            temperature_limit=85.0,
                        ),
                        OperationMode.SAFE: ComponentConfig(
                            power_consumption=20.0,
                            temperature_limit=70.0,
                        ),
                    },
                ),
            ),
        ),
    }

    # Evaluate
    results = vq.evaluate_project(project, input_data)

    # Export to TOML
    output_path = tmp_path / "output.toml"
    vq.export_to_toml(project, input_data, results, output_path)

    # Read the TOML file and verify its structure
    with output_path.open("rb") as f:
        toml_data = tomllib.load(f)

    # Verify the structure matches expectations
    assert "Component" in toml_data
    assert "model" in toml_data["Component"]
    assert "design" in toml_data["Component"]["model"]
    assert toml_data["Component"]["model"]["design"]["name"] == "TestComponent"

    # Verify the configs table is properly serialized
    assert "configs" in toml_data["Component"]["model"]["design"]
    configs = toml_data["Component"]["model"]["design"]["configs"]

    # Check that the table keys are strings (enum values)
    assert "nominal" in configs
    assert "safe" in configs

    # Check that the BaseModel values are serialized as dicts
    assert isinstance(configs["nominal"], dict)
    assert configs["nominal"]["power_consumption"] == 100.0
    assert configs["nominal"]["temperature_limit"] == 85.0

    assert isinstance(configs["safe"], dict)
    assert configs["safe"]["power_consumption"] == 20.0
    assert configs["safe"]["temperature_limit"] == 70.0

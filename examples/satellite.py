import json
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel
from rich import print  # noqa: A004

import veriq as vq


class CommunicationSubsystemModel(BaseModel):
    """Model for the communication subsystem."""

    frequency: float


@vq.calculation
def calculate_bandwidth(model: CommunicationSubsystemModel) -> float:
    """Calculate the bandwidth of the communication subsystem."""
    # Here we would implement the actual calculation logic.
    return model.frequency * 2  # Example calculation


@vq.verification
def verify_telemetry_function(bandwidth: Annotated[float, vq.Depends(calculate_bandwidth)]) -> bool:
    """Verify the telemetry function of the communication subsystem."""
    # Here we would implement the actual verification logic.
    return bandwidth > 1000  # Example condition


class GroundStationModel(BaseModel):
    """Model for the ground station."""

    location: str
    antenna_size: float


@vq.verification
def verify_ground_station(model: GroundStationModel) -> bool:
    """Verify the ground station model."""
    # Here we would implement the actual verification logic.
    return model.antenna_size > 0


def ground_station_requirement() -> vq.Requirement:
    """Requirement factory function for the ground station."""
    return vq.Requirement(
        "The ground station shall be able to receive telemetry data from the satellite.",
        verified_by=verify_ground_station,
    )


satellite = vq.Scope("Satellite")
# There should be one instance of a Model per Scope.
# If you want to have multiple instances of a CommunicationSubsystemModel,
# you need to create a new Scope for each instance, or you can define a parent model like this:
# class ParentModel(BaseModel):
#     child_models: list[ChildModel]

with satellite:
    # Requirements definition
    req_comm = vq.Requirement("The satellite shall communicate with the ground station.")
    with req_comm:
        vq.Requirement("The satellite shall transmit telemetry data.", verified_by=verify_telemetry_function)
        vq.Requirement(
            "The satellite shall receive commands from the ground station.",
        )  # No verification method provided!
        ground_station_requirement()  # reuses the ground station requirement defined earlier

print("Satellite Scope Requirements:")
for req in satellite.iter_requirements():
    print(req)

print("\nLeaf Requirements in Satellite Scope:")
for req in satellite.iter_leaf_requirements():
    # Leaf requirements are those that do not have any child requirements.
    # Leaf requirements should be associated with verification method.
    print(req)

print("\nModels in Satellite Scope:")
for model in satellite.iter_models():
    print(model)


@satellite.model_compatibility
def check_models_compatibility(comm_model: CommunicationSubsystemModel, ground_model: GroundStationModel) -> bool:
    """Check if the communication subsystem and ground station models are compatible."""
    # Here we would implement the actual compatibility check logic.
    return True


print("\nModel Compatibility Checks:")
for compatibility in satellite.model_compatibilities:
    print(f"{compatibility.model_a.__name__} and {compatibility.model_b.__name__} compatibility: {compatibility.func}")

print("\nSatellite Model:")
DesignModel = satellite.design_model(include_child_scopes=True, leaf_only=True)
print(DesignModel)

design_schema = satellite.design_json_schema(include_child_scopes=True, leaf_only=True)
schema_path = Path(__file__).parent / ".veriq" / Path(__file__).stem / "Satellite-design-schema.json"
schema_path.parent.mkdir(parents=True, exist_ok=True)
with schema_path.open("w") as f:
    json.dump(design_schema, f, indent=2)


design = DesignModel(
    CommunicationSubsystemModel=CommunicationSubsystemModel(frequency=1500.0),
    GroundStationModel=GroundStationModel(location="Cape Canaveral", antenna_size=5.0),
)


result = satellite.verify_design(design)
print("Design verification result:", result)

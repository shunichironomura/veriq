from typing import Annotated

from pydantic import BaseModel

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


@satellite.model_compatibility
def check_models_compatibility(comm_model: CommunicationSubsystemModel, ground_model: GroundStationModel) -> bool:
    """Check if the communication subsystem and ground station models are compatible."""
    # Here we would implement the actual compatibility check logic.
    return True

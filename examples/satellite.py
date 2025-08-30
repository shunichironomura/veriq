import logging
from typing import Annotated

from pydantic import BaseModel

import veriq as vq

logging.basicConfig(level=logging.DEBUG)


class CommunicationSubsystem(BaseModel):
    """Model for the communication subsystem."""

    frequency: float


@vq.calculation
def calculate_bandwidth(model: CommunicationSubsystem) -> float:
    """Calculate the bandwidth of the communication subsystem."""
    # Here we would implement the actual calculation logic.
    return model.frequency * 2  # Example calculation


@vq.verification
def verify_telemetry_function(bandwidth: Annotated[float, vq.Depends(calculate_bandwidth)]) -> bool:
    """Verify the telemetry function of the communication subsystem."""
    # Here we would implement the actual verification logic.
    return bandwidth > 1000  # Example condition


class GroundStation(BaseModel):
    """Model for the ground station."""

    location: str
    antenna_size: float


@vq.verification
def verify_ground_station(model: GroundStation) -> bool:
    """Verify the ground station model."""
    # Here we would implement the actual verification logic.
    return model.antenna_size > 0


class AOCS(BaseModel):
    """Model for the Attitude and Orbit Control System (AOCS)."""

    three_axis_stabilized: bool


@vq.verification
def verify_three_axis_stabilization(model: AOCS) -> bool:
    """Verify the three-axis stabilization of the AOCS."""
    # Here we would implement the actual verification logic.
    return model.three_axis_stabilized


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
    req_att = vq.Requirement(
        "The satellite shall have an three-axis stabilized attitude control system.",
        verified_by=verify_three_axis_stabilization,
    )
    with vq.Scope("Communication"):
        req_comm = vq.Requirement("The satellite shall communicate with the ground station.")
        with req_comm:
            vq.Requirement(
                "The satellite shall receive commands from the ground station.",
            )  # No verification method provided!
            ground_station_requirement()  # reuses the ground station requirement defined earlier
            vq.depends(req_att)
            req_tx = vq.Requirement(
                "The satellite shall transmit telemetry data.",
                verified_by=verify_telemetry_function,
            )


@satellite.model_compatibility
def check_models_compatibility(comm_model: CommunicationSubsystem, ground_model: GroundStation) -> bool:
    """Check if the communication subsystem and ground station models are compatible."""
    # Here we would implement the actual compatibility check logic.
    return True


if __name__ == "__main__":
    import tomllib
    from pathlib import Path

    include_child_scopes = True
    leaf_only = False

    from rich import print

    print(list(satellite.iter_requirements(include_child_scopes=include_child_scopes, leaf_only=leaf_only)))
    print(list(satellite.iter_verifications(include_child_scopes=include_child_scopes, leaf_only=leaf_only)))
    print(list(satellite.iter_models(include_child_scopes=include_child_scopes, leaf_only=leaf_only)))

    DesignModel = satellite.design_model(include_child_scopes=include_child_scopes, leaf_only=leaf_only)

    design_file_path = Path(__file__).parent / "satellite.py.design.toml"
    with design_file_path.open("rb") as f:
        design_data = DesignModel.model_validate(tomllib.load(f))

    verification_result = satellite.verify_design(
        design_data,
        include_child_scopes=include_child_scopes,
        leaf_only=leaf_only,
    )
    print(verification_result)

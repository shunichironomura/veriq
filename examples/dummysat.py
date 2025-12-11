from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel

import veriq as vq

project = vq.Project("Project")

system = vq.Scope("System")
thermal = vq.Scope("Thermal")
power = vq.Scope("Power")
aocs = vq.Scope("AOCS")
rwa = vq.Scope("RWA")

project.add_scope(system)
project.add_scope(aocs)
project.add_scope(power)
project.add_scope(thermal)
project.add_scope(rwa)


class OperationMode(StrEnum):
    NOMINAL = "nominal"
    SAFE = "safe"
    MISSION = "mission"


class OperationPhase(StrEnum):
    INITIAL = "initial"
    CRUISE = "cruise"


@system.root_model()
class SatelliteModel(BaseModel):
    pass


@aocs.root_model()
class AOCSModel(BaseModel):
    # reaction_wheel_assembly: ReactionWheelAssemblyModel
    design: AOCSDesign
    requirement: AOCSRequirement


class AOCSDesign(BaseModel): ...


@rwa.root_model()
class ReactionWheelAssemblyModel(BaseModel):
    wheel_x: ReactionWheelModel
    wheel_y: ReactionWheelModel
    wheel_z: ReactionWheelModel

    # required by PowerInterface
    power_consumption: vq.Table[OperationMode, float]
    peak_power_consumption: vq.Table[tuple[OperationPhase, OperationMode], float]

    # required by StructuralInterface
    mass: float


class ReactionWheelModel(BaseModel):
    max_torque: float  # in Nm
    power_consumption: float  # in Watts
    mass: float  # in kg


class AOCSRequirement(BaseModel): ...


# - There should be at most one model per scope.
@power.root_model()
class PowerSubsystemModel(BaseModel):
    design: PowerSubsystemDesign
    requirement: PowerSubsystemRequirement


class PowerSubsystemDesign(BaseModel):
    battery_a: BatteryModel
    battery_b: BatteryModel
    solar_panel: SolarPanelModel


class PowerSubsystemRequirement(BaseModel): ...


class BatteryModel(BaseModel):
    capacity: float  # in Watt-hours


class SolarPanelModel(BaseModel):
    area: float  # in square meters
    efficiency: float  # as a fraction


class SolarPanelResult(BaseModel):
    heat_generation: float  # in Watts


@thermal.root_model()
class ThermalModel(BaseModel): ...


class ThermalResult(BaseModel):
    solar_panel_temperature_max: float  # in Celsius


@system.verification(imports=["Power", "Thermal"])
def power_thermal_compatibility(
    power_model: Annotated[PowerSubsystemModel, vq.Ref("$", scope="Power")],
    thermal_model: Annotated[ThermalModel, vq.Ref("$", scope="Thermal")],
) -> bool:
    """Verify the compatibility between power and thermal subsystems."""
    # Here we would implement the actual verification logic.
    return True  # Example condition


# Lookup order
# 1. Determine the scope. If not specified, use the scope of the function decorator.
# 2. If it has an accessor, use the accessor to get the model.
# 3. Otherwise, look for the model in the determined scope.
#    There should be at most one use of the model in that scope, or an error is raised.
@power.verification()
def verify_battery(
    first_battery: Annotated[BatteryModel, vq.Ref("$.design.battery_a")],
) -> bool:
    return first_battery.capacity > 50.0  # Example condition


@thermal.calculation(imports=["Power"])
def calculate_temperature(
    solar_panel_heat_generation: Annotated[
        float,
        vq.Ref("@calculate_solar_panel_heat.heat_generation", scope="Power"),
    ],
) -> ThermalResult:
    """Calculate the thermal result based on the thermal model and solar panel result."""
    # Here we would implement the actual calculation logic.
    temperature = solar_panel_heat_generation * 0.5  # Example calculation
    return ThermalResult(solar_panel_temperature_max=temperature)


@power.verification(imports=["Thermal"], xfail=True)
def solar_panel_max_temperature(
    solar_panel_temperature_max: Annotated[
        float,
        vq.Ref("@calculate_temperature.solar_panel_temperature_max", scope="Thermal"),
    ],
) -> bool:
    """Assert that the solar panel maximum temperature is within limits."""
    # Here we would implement the actual assertion logic.
    return solar_panel_temperature_max < 45  # Example limit


@power.calculation()
@vq.assume(solar_panel_max_temperature)
def calculate_solar_panel_heat(
    solar_panel: Annotated[SolarPanelModel, vq.Ref("$.design.solar_panel")],
) -> SolarPanelResult:
    """Calculate the heat generation of the solar panel."""
    # Here we would implement the actual calculation logic.
    heat_generation = 100.0  # Example calculation
    return SolarPanelResult(heat_generation=heat_generation)


# The following requirement definitions are in a different module in practice.
with system.requirement("REQ-SYS-001", "Some system-level requirement."):
    system.requirement("REQ-SYS-002", "Thermal requirement for solar panel temperature.")
    system.requirement("REQ-SYS-003", "Power requirement for battery performance.")

with system.fetch_requirement("REQ-SYS-002"):
    thermal.requirement(
        "REQ-TH-001-1",
        "Sub-requirement for thermal model accuracy.",
        verified_by=[
            solar_panel_max_temperature,
        ],
    )
    vq.depends(system.fetch_requirement("REQ-SYS-001"))

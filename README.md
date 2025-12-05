# veriq — Requirements Verification Tool

> [!WARNING]
> This package is still under active development.
> There are known issues and limitations.

- [日本語 readme](https://github.com/shunichironomura/veriq/blob/main/README.ja.md)

`veriq` helps you manage requirements, calculations, and verifications across an engineering project. Think of it as a smart spreadsheet that tracks dependencies between calculations and automatically verifies that requirements are met.

## Quick Start

Install veriq:

```bash
pip install veriq
```

## Understanding veriq: The Spreadsheet Analogy

If you've used spreadsheets like Excel, you already understand the core concepts of veriq:

### Spreadsheet → veriq Concepts

| Spreadsheet                      | veriq            | Description                                                |
| -------------------------------- | ---------------- | ---------------------------------------------------------- |
| **Workbook**                     | **Project**      | The top-level container for everything                     |
| **Sheet**                        | **Scope**        | A logical grouping (e.g., "Power", "Thermal", "Structure") |
| **Input cells**                  | **Model**        | Design parameters you provide (like battery capacity)      |
| **Formula cells**                | **Calculation**  | Computed values (like `=B2*0.3`)                           |
| **Conditional formatting rules** | **Verification** | Checks that values meet requirements (like `<=85`)         |

Just like a spreadsheet:

- You input your design parameters (model data)
- veriq calculates derived values automatically
- It checks whether requirements are satisfied
- Changes propagate through the dependency chain

The key difference? veriq can handle complex engineering calculations with proper types and requirement traceability.

## Tutorial: Building a Satellite Thermal-Power Analysis

Let's build a simple satellite subsystem analysis step by step. We'll model solar panels that generate heat, and verify that the temperature stays within limits.

### Step 1: Create Your Project Structure

Create a new Python file `my_satellite.py`:

```python
import veriq as vq
from pydantic import BaseModel
from typing import Annotated

# Create a project (like creating a new workbook)
project = vq.Project("MySatellite")

# Create scopes (like creating sheets)
power = vq.Scope("Power")
thermal = vq.Scope("Thermal")

# Add scopes to the project
project.add_scope(power)
project.add_scope(thermal)
```

### Step 2: Define Your Design Models (Input Cells)

Design models are the input parameters you'll provide. Define them using Pydantic models:

```python
# Define what data the Power subsystem needs
@power.root_model()
class PowerModel(BaseModel):
    solar_panel_area: float  # in square meters
    solar_panel_efficiency: float  # 0.0 to 1.0

# Define what data the Thermal subsystem needs
@thermal.root_model()
class ThermalModel(BaseModel):
    pass  # No inputs needed for this example
```

### Step 3: Add Calculations (Formula Cells)

Calculations are like spreadsheet formulas. They take inputs and compute outputs:

```python
# Define the output of a calculation
class SolarPanelOutput(BaseModel):
    power_generated: float  # in Watts
    heat_generated: float  # in Watts

# Create a calculation in the Power scope
@power.calculation()
def calculate_solar_panel(
    solar_panel_area: Annotated[float, vq.Ref("$.solar_panel_area")],
    solar_panel_efficiency: Annotated[float, vq.Ref("$.solar_panel_efficiency")],
) -> SolarPanelOutput:
    """Calculate power and heat from solar panels."""
    # Assume 1000 W/m² solar flux
    power_in = solar_panel_area * 1000.0
    power_out = power_in * solar_panel_efficiency
    heat_out = power_in - power_out

    return SolarPanelOutput(
        power_generated=power_out,
        heat_generated=heat_out,
    )
```

**Note the `vq.Ref()` annotation:**

- `"$"` means "root of the current scope"
- `"$.solar_panel_area"` means "the `solar_panel_area` field in the Power model"

Now add a thermal calculation that uses the power calculation result:

```python
class ThermalOutput(BaseModel):
    solar_panel_temperature: float  # in Celsius

@thermal.calculation(imports=["Power"])
def calculate_temperature(
    heat_generated: Annotated[
        float,
        vq.Ref("@calculate_solar_panel.heat_generated", scope="Power")
    ],
) -> ThermalOutput:
    """Calculate temperature based on heat generated."""
    # Simplified thermal model
    temperature = heat_generated * 0.05  # 0.05 °C per Watt
    return ThermalOutput(solar_panel_temperature=temperature)
```

**New concepts:**

- `imports=["Power"]` tells veriq this calculation needs data from the Power scope
- `scope="Power"` specifies where to look for the referenced value
- `"@calculate_solar_panel"` refers to a calculation (using `@` prefix)

### Step 4: Add Verifications (Requirement Checks)

Verifications are like conditional formatting rules that check if values meet requirements:

```python
@thermal.verification(imports=["Power"])
def solar_panel_temperature_limit(
    temperature: Annotated[
        float,
        vq.Ref("@calculate_temperature.solar_panel_temperature")
    ],
) -> bool:
    """Verify that solar panel temperature is within limits."""
    MAX_TEMP = 85.0  # degrees Celsius
    return temperature <= MAX_TEMP
```

### Step 5: Create Your Input File

Create a TOML file `my_satellite.in.toml` with your design parameters:

```toml
[Power.model]
solar_panel_area = 2.0
solar_panel_efficiency = 0.3

[Thermal.model]
# No inputs needed
```

### Step 6: Check Your Project

Verify that your project structure is valid:

```bash
veriq check my_satellite.py
```

You should see:

```
Loading project from script: my_satellite.py
Project: MySatellite

Validating dependencies...

╭──────────────────────── Project: MySatellite ────────────────────────╮
│ ┏━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓                           │
│ ┃ Scope   ┃ Calculations ┃ Verifications ┃                           │
│ ┡━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩                           │
│ │ Power   │            1 │             0 │                           │
│ │ Thermal │            1 │             1 │                           │
│ └─────────┴──────────────┴───────────────┘                           │
╰────────────────────────────────────────── 2 scopes ──────────────────╯

✓ Project is valid
```

### Step 7: Run Calculations and Verifications

Calculate all results and verify requirements:

```bash
veriq calc my_satellite.py -i my_satellite.in.toml -o my_satellite.out.toml --verify
```

You should see:

```
Loading project from script: my_satellite.py
Project: MySatellite

Loading input from: my_satellite.in.toml
Evaluating project...

╭──────────────────── Verification Results ────────────────────╮
│  Verification                                Result          │
│  Thermal::?solar_panel_temperature_limit     ✓ PASS          │
╰───────────────────────────────────────────────────────────────╯

Exporting results to: my_satellite.out.toml

✓ Calculation complete
```

### Step 8: View Your Results

Open `my_satellite.out.toml` to see all calculated values:

```toml
[Power.model]
solar_panel_area = 2.0
solar_panel_efficiency = 0.3

[Power.calc.calculate_solar_panel]
power_generated = 600.0
heat_generated = 1400.0

[Thermal.calc.calculate_temperature]
solar_panel_temperature = 70.0

[Thermal.verification]
solar_panel_temperature_limit = true
```

The output file contains:

- All input values (model)
- All calculated values (calc)
- All verification results (verification)

## Core Concepts Reference

### Project and Scopes

A **Project** is the top-level container. **Scopes** organize your system into logical subsystems:

```python
project = vq.Project("SatelliteName")

# Create scopes for different subsystems
power = vq.Scope("Power")
thermal = vq.Scope("Thermal")
structure = vq.Scope("Structure")

project.add_scope(power)
project.add_scope(thermal)
project.add_scope(structure)
```

### Models (Design Parameters)

**Models** define the input data structure for each scope using Pydantic:

```python
@power.root_model()
class PowerModel(BaseModel):
    battery_capacity: float  # in Watt-hours
    solar_panel_area: float  # in square meters
```

### Calculations

**Calculations** are functions that compute derived values. They automatically track dependencies:

```python
class BatteryOutput(BaseModel):
    max_discharge_power: float

@power.calculation()
def calculate_battery_performance(
    capacity: Annotated[float, vq.Ref("$.battery_capacity")],
) -> BatteryOutput:
    max_power = capacity * 0.5  # Example: 0.5C discharge rate
    return BatteryOutput(max_discharge_power=max_power)
```

### Verifications

**Verifications** check that requirements are met. They return `True` if passing, `False` if failing:

```python
@power.verification()
def verify_battery_capacity(
    capacity: Annotated[float, vq.Ref("$.battery_capacity")],
) -> bool:
    MIN_CAPACITY = 100.0  # Wh
    return capacity >= MIN_CAPACITY
```

### References (`vq.Ref`)

References tell veriq where to find data. The syntax is:

- `"$"` - Root of current scope model
- `"$.field.subfield"` - Navigate through model structure
- `"@calculation_name.output_field"` - Reference a calculation output
- `scope="ScopeName"` - Look in a different scope
- `imports=["ScopeName"]` - Declare scope dependencies

Examples:

```python
vq.Ref("$.battery_capacity")  # Current scope's model
vq.Ref("@calculate_power.max_power")  # Current scope's calculation
vq.Ref("$.battery_capacity", scope="Power")  # Different scope's model
vq.Ref("@calculate_temp.max_temp", scope="Thermal")  # Different scope's calculation
```

### Tables (Multi-dimensional Data)

Use **Tables** for data indexed by enums (like operating modes):

```python
from enum import StrEnum

class OperationMode(StrEnum):
    NOMINAL = "nominal"
    SAFE = "safe"

class PowerModel(BaseModel):
    # Table indexed by operating mode
    power_consumption: vq.Table[OperationMode, float]
```

In your TOML file:

```toml
[Power.model.power_consumption]
nominal = 50.0
safe = 10.0
```

For multi-dimensional tables:

```python
class OperationPhase(StrEnum):
    LAUNCH = "launch"
    ORBIT = "orbit"

class PowerModel(BaseModel):
    # Table indexed by (phase, mode)
    peak_power: vq.Table[tuple[OperationPhase, OperationMode], float]
```

In your TOML file:

```toml
[Power.model.peak_power]
"launch,nominal" = 100.0
"launch,safe" = 20.0
"orbit,nominal" = 80.0
"orbit,safe" = 15.0
```

## CLI Reference

### `veriq check`

Check that your project structure is valid without running calculations:

```bash
# Check a Python script
veriq check my_satellite.py

# Check a module (if installed as package)
veriq check my_package.my_satellite:project

# Specify project variable explicitly
veriq check my_satellite.py --project my_project

# Verbose mode
veriq --verbose check my_satellite.py
```

### `veriq calc`

Run calculations and optionally verify requirements:

```bash
# Basic calculation
veriq calc my_satellite.py -i input.toml -o output.toml

# With verification
veriq calc my_satellite.py -i input.toml -o output.toml --verify

# Using module path
veriq calc my_package.my_satellite:project -i input.toml -o output.toml

# Verbose mode
veriq --verbose calc my_satellite.py -i input.toml -o output.toml
```

**Options:**

- `-i, --input`: Path to input TOML file (required)
- `-o, --output`: Path to output TOML file (required)
- `--verify`: Run verifications and exit with error if any fail
- `--project`: Name of the project variable (for script paths)
- `--verbose`: Show detailed debug information

**Exit codes:**

- `0`: Success (calculations complete, all verifications passed if `--verify` used)
- `1`: Failure (verifications failed, or error occurred)

## Advanced Example

See [examples/dummysat.py](examples/dummysat.py) for a complete example showing:

- Multiple interconnected scopes
- Cross-scope calculations
- Complex verifications
- Table usage for multi-dimensional data
- Requirement definitions and traceability

## Development Status

This project is under active development. Current features:

- ✅ Define projects, scopes, and models
- ✅ Create calculations with automatic dependency tracking
- ✅ Define and run verifications
- ✅ Export/import design data via TOML
- ✅ CLI for checking projects and running calculations
- 🚧 Requirement traceability (partial)
- 🚧 Visualization of dependency graphs

## Contributing

Contributions are welcome! Please note that this project is in early development and APIs may change.

## License

MIT License

## Acknowledgement

veriq originated in the `shunichironomura/veriq` repository, and its early development up to version v0.0.1 was supported by ArkEdge Space Inc.

# veriq — Requirements verification tool

> [!WARNING]
> This package is still under active development.
> There are still known issues and limitations.

`veriq` manages requirements, design, and verification of an engineering system.

## Usage

### Defining Requirements

You can define requirements tree, verification functions, and design models.

See [examples/satellite.py](examples/satellite.py) for a complete example.

### Generating Design Schema

You can generate a JSON schema for your design models using the `veriq` CLI.

```bash
veriq schema satellite.py
```

This will create a `satellite.py.schema.json` file in the same directory as `satellite.py`.

### Defining the Design

You can define your design as a TOML file `satellite.py.design.toml`.

### Verifying Requirements

You can verify your requirements using the `veriq` CLI.

```bash
veriq verify satellite.py
```

This will read the requirements, verifications, and design models from `satellite.py` and the design from `satellite.py.design.toml`, and perform the verification.

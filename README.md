# TCT Laser Measurements

A measurement application for TCT laser setups.

## Running the Application

Start the application with:

```bash
uv run tct-laser
```

## Local Development

For local development without physical instruments, start the instrument emulators:

```bash
uv run comet-emulator
```

## Emulator Configuration

The emulator ports and instrument connection settings are defined in `emulators.yaml`.

Update this file to configure the ports and connection parameters used by the application and instrument emulators.

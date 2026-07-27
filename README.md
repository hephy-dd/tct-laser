# TCT Laser Measurements

A measurement application for TCT laser setups.

## Prerequisites

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), Astral's Python package manager, before getting started. This project uses `uv` for development, running the application, and packaging.

## Getting Started

Clone the repository and run the application directly with:

```bash
uv run tct-laser
```

The first run automatically creates a virtual environment (if needed) and installs the project's dependencies.

## Local Development

When developing without physical instruments, start the instrument emulators in a separate terminal:

```bash
uv run comet-emulator
```

Then start the measurement application:

```bash
uv run tct-laser
```

## Emulator Configuration

The instrument emulators read their connection settings from `emulators.yaml`.

Modify this file to configure the emulator ports and the corresponding instrument connection parameters for your local environment.

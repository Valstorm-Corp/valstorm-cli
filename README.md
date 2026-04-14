# Valstorm CLI

A local command-line interface for Valstorm developers.

## Prerequisites

- [uv](https://github.com/astral-sh/uv) installed on your machine.

## Usage

### Run from the Monorepo Root
The recommended way to run the CLI while developing is using `uv run` from the root:

```bash
uv run --project cli valstorm --help
```

To check the API status:
```bash
uv run --project cli valstorm status
```

### Run from the CLI Directory
You can also run it directly from this folder:

```bash
cd cli
uv run valstorm status
```

## Local Installation (Optional)

If you want the `valstorm` command to be available globally in your terminal without using `uv run`, you can install it in editable mode:

```bash
uv tool install --editable cli/
```

Now you can just run:
```bash
valstorm status
```

## Commands

- `status`: Checks if the Valstorm API is live.

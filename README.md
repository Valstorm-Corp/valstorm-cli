# Valstorm CLI

A local command-line interface for Valstorm developers to authenticate via OAuth 2.1 + PKCE, pull and push object schemas as code, and manage local workspaces.

- **Official Tool Page & Quickstart:** [https://www.valstorm.com/free-tools/valstorm-cli](https://www.valstorm.com/free-tools/valstorm-cli?utm_source=github&utm_medium=readme&utm_campaign=valstorm_cli)
- **All Valstorm Free & Open-Source Tools:** [https://www.valstorm.com/free-tools](https://www.valstorm.com/free-tools?utm_source=github&utm_medium=readme&utm_campaign=valstorm_cli)
- **Valstorm BOS Platform Overview:** [https://www.valstorm.com/bos](https://www.valstorm.com/bos?utm_source=github&utm_medium=readme&utm_campaign=valstorm_cli)
- **Valstorm Pricing & Self-Serve Workspace:** [https://www.valstorm.com/pricing](https://www.valstorm.com/pricing?utm_source=github&utm_medium=readme&utm_campaign=valstorm_cli)

## Prerequisites

- [uv](https://github.com/astral-sh/uv) installed on your machine (`curl -LsSf https://astral.sh/uv/install.sh | sh`).
- Ensure `$HOME/.local/bin` is added to your `PATH` (executables installed via `uv tool` reside in `~/.local/bin`):
  ```bash
  # For zsh (default on macOS):
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc

  # For bash:
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
  ```

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

## Installation

To install the `valstorm` command globally, use `uv tool install` directly from GitHub:

```bash
uv tool install git+https://github.com/Valstorm-Corp/valstorm-cli
```

Now you can just run:
```bash
valstorm status
```

## Commands

- `status`: Checks if the Valstorm API is live.

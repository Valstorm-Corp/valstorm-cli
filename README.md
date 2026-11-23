# Open Valstorm CLI (`valstorm-cli`)

A focused developer CLI for **Open Valstorm** (`apps/open-api`, `apps/open-worker`, and self-hosted or hosted instances).

## Installation

```bash
# Install via uv (recommended)
uv tool install git+https://github.com/Valstorm-Corp/valstorm-cli.git

# Or run directly inside the monorepo
uv run --project apps/cli valstorm --help
```

Optional MCP server extra:

```bash
pip install "valstorm-cli[mcp] @ git+https://github.com/Valstorm-Corp/valstorm-cli.git"
```

## Quick Start

```bash
# Authenticate (hosted or self-hosted Open Valstorm)
valstorm login
valstorm login --url https://api.acme.internal
valstorm login --pat pat_... --url https://api.acme.internal

# Initialize a local workspace & sync metadata/schemas
valstorm init
valstorm pull
valstorm push --dry-run

# Inspect PostgreSQL schema drift & sync migrations (Alembic/Prisma/SQL)
valstorm schema status
valstorm schema sync

# Query data (raw lookup IDs by default; pass --hydrate for {id, name})
valstorm sql "SELECT id, name, owner FROM contact LIMIT 10"
valstorm sql "SELECT id, name, owner FROM contact LIMIT 10" --hydrate
valstorm graphql "{ contact(limit: 5) { id name owner { id name } } }"
valstorm graphql "{ contact(limit: 5) { id name owner { id name } } }" --hydrate

# Validate & execute serverless Python functions
valstorm fn list
valstorm fn validate function/my_handler.py
valstorm fn run function/my_handler.py --input '{"hello": "world"}'

# Discover & invoke PlatformContext / plugin RPC methods
valstorm rpc list --namespace utils
valstorm rpc call utils.ping -a message=hello
```

## Command Overview

| Group / Command | Description |
|---|---|
| `status`, `version`, `update`, `init` | API health, CLI version/upgrade, workspace scaffolding |
| `login`, `auth` | OAuth2 PKCE / PAT login (`--url` for self-hosted), profiles, `whoami`, `pat` management |
| `project` | `open` web app, `update-stubs` |
| `pull`, `push` | Single-roundtrip ACID metadata & schema sync (`/v1/apps/metadata/pull`, `/push`) |
| `schema` | `list`, `get`, `create`, `update`, `delete`, `status` (PG drift), `sync` (PG reflection), `field` |
| `record` | `get` (default raw IDs; `--hydrate`), `create`, `update`, `delete`, `restore` |
| `sql`, `graphql` | Execute SQL / GraphQL queries (default raw IDs; pass `--hydrate` for `{id, name}`) |
| `fn` | `list`, `validate`, `run` serverless Python functions |
| `app` | `list`, `envs`, `install`, `uninstall`, `package`, `deploy`, `promote`, `publish` |
| `sandbox` | `list`, `create`, `refresh`, `delete`, `use [--parent]`, `users add\|remove` |
| `vfs` | `ls`, `info`, `upload`, `download`, `mv`, `rm`, `index` |
| `search`, `ask` | Hybrid pgvector + BM25 search and streaming RAG Q&A |
| `rpc` | `list`, `call` universal PlatformContext & plugin RPC methods |

## Environment Variables

| Variable | Purpose |
|---|---|
| `VALSTORM_API_URL` | Override API base URL (for self-hosted Open Valstorm instances) |
| `VALSTORM_WEB_URL` | Override web app base URL for browser OAuth |
| `VALSTORM_TOKEN` / `VALSTORM_API_KEY` | Headless Bearer/PAT token for CI/CD |
| `VALSTORM_ENV` | Environment label (`prod`, `dev`, `local`, or custom) |
| `VALSTORM_PROFILE` | Auth profile name (`default` or custom) |

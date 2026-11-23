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

## Multi-Org Workspace Layout

Each org gets its own self-contained folder with `valstorm.json` inside it, so you can manage multiple orgs side-by-side simply by opening terminals in each folder:

```bash
valstorm init acme-prod --profile acme --env prod
cd acme-prod
valstorm pull
```

```text
acme-prod/
├── valstorm.json                 # Org-scoped env/profile/api_url/sandbox/objects
├── .gitignore                    # Ignores .valstorm/ local sync state
├── schemas/                      # Object schemas (<api_name>.json)
├── app/                          # app (*.json)
├── record_trigger/               # record_trigger (*.py)
├── function/                     # function (*.py)
├── schedule_trigger_setting/     # schedule_trigger_setting (*.json)
├── permission/                   # permission (*.json)
├── role/                         # role (*.json)
└── queries/                      # Created lazily on `sql`/`graphql` --save
```

Optional `init` flags:
- `--minimal`: create only `valstorm.json` and `.gitignore`.
- `--ai`: also generate opt-in `.mcp.json` (via `uvx valstorm-mcp`) and `CLAUDE.md`.
- `--url`: bind a self-hosted Open Valstorm API URL.

## Quick Start

```bash
# Authenticate (hosted or self-hosted Open Valstorm)
valstorm login
valstorm login --url https://api.acme.internal
valstorm login --pat pat_... --url https://api.acme.internal

# Open the active org in your browser
valstorm open

# Sync metadata & schemas in one roundtrip
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
| `init`, `open`, `status`, `version`, `update` | Org workspace setup, open in browser, API health, CLI version/upgrade |
| `login`, `auth` | OAuth2 PKCE / PAT login (`--url` for self-hosted), profiles, `whoami`, `pat` management |
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

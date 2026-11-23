# Open Valstorm CLI — Developer Guide

Python CLI (`apps/cli`) built with Typer, Rich, `httpx`, and `valstorm-client` (`packages/client-python`) targeting the Open Valstorm core (`apps/open-api`).

## Running Locally

```bash
uv run --project apps/cli valstorm --help
uv run --project apps/cli pytest apps/cli/tests
```

## Module Layout (`apps/cli/src/valstorm_cli/`)

- `main.py` — Root Typer app, `init`, `open`, `status`, `version`, `update`, and command registration.
- `auth.py`, `auth_cmds.py` — OAuth2 PKCE + PAT auth, multi-profile management, custom self-hosted URL resolution (`VALSTORM_API_URL`, `--url`), and `auth pat` management.
- `sync.py` — Single-roundtrip ACID `pull` and `push` via `/v1/apps/metadata/pull` and `/v1/apps/metadata/push` (`sdk.apps`). Defaults to the 6 standard object `api_name`s (`app`, `record_trigger`, `function`, `schedule_trigger_setting`, `permission`, `role`) plus `schemas`.
- `query.py` — `sql` and `graphql` commands. Both default to **no hydration** (`hydrate=False`), returning raw string IDs unless `--hydrate` is explicitly passed. Saves/loads relative query files under `<org-root>/queries/`.
- `record.py` — `record get` (default `hydrate=False`), `create`, `update`, `delete`, and `restore` (`/v1/object/{api}/undelete`).
- `schema.py`, `field.py` — Schema/field CRUD plus Open Valstorm PostgreSQL drift detection (`schema status`) and migration reflection (`schema sync`).
- `fn_cmds.py` — `fn list`, `fn validate` (AST gatekeeper dry-run), and `fn run` (local file, function ID, or name).
- `app_cmds.py` — `app list`, `envs`, `install`, `uninstall`, `package`, `deploy`, `promote`, and `publish` via `sdk.apps`.
- `rpc_cmds.py` — `rpc list` and `rpc call` for universal `/v1/platform/methods` and `/v1/platform/invoke/{target}`.
- `sandbox.py` — `sandbox list`, `create`, `refresh`, `delete`, `use [--parent]`, and `users add|remove`.
- `vfs_cmds.py` — Slimmed VFS operations (`ls`, `info`, `upload`, `download`, `mv`, `rm`, `index`).
- `search_cmds.py` — Hybrid `search` and streaming RAG `ask`.
- `bundler.py`, `git_utils.py`, `manifest_builder.py` — Workspace bundling and git-diff manifest helpers aligned to `<org-root>/<api_name>/`.

## Auth & Multi-Org Workspaces

- Each org initialized via `valstorm init <name>` gets its own `<name>/valstorm.json`, so running commands inside each folder targets that org automatically.
- Auth tokens live in `~/.valstorm/auth_{env}_{profile}.json` (including optional `api_url` / `web_url`) and are shared with `apps/valstorm-mcp-server`.

# Valstorm Developer CLI - AI Context

## Project Overview
This is the Valstorm Developer CLI, a Python-based command-line tool for developers to interact with the Valstorm platform. It is used to manage authentication, bootstrap local projects, and synchronize metadata (record triggers, functions, schemas, apps, AI agents, permissions, etc.) between the local filesystem and the Valstorm cloud.

## Tech Stack
- **CLI Framework:** Typer
- **Console UI:** Rich (for formatted terminal output)
- **HTTP Client:** HTTPX (synchronous calls to Valstorm API)
- **Package Manager:** uv

## Core Architecture
- **Authentication (`auth.py`):** 
  - Manages tokens using OAuth2 password flow. 
  - Supports multiple profiles and environments (`prod`, `dev`, `local`). 
  - Credentials are saved in `~/.valstorm/auth_{env}_{profile}.json`.
- **Command Entrypoint (`main.py`):** 
  - Uses `@app.command()` for root commands (`login`, `pull`, `push`, `init`).
  - Uses `@auth_app.command()` for the `auth` subcommand group (`list`, `switch`).
- **Local Project Structure:** 
  - Initialized via `valstorm init`. 
  - Creates an `object/` directory (for extracted code and JSON metadata arrays) and a `schemas/` directory (for JSON object schemas).
  - Keeps track of target environment and profile in `valstorm.json`.

## Development Guidelines
- **Adding Commands:** Define commands in `main.py`. Keep logic concise.
- **API Interaction:** 
  - Always instantiate `auth = ValstormAuth(...)` to grab current targets.
  - Call `auth.ensure_valid_token()` before making requests.
  - Use `auth.get_client()` to get a pre-configured `httpx.Client` with bearer auth attached.
- **User Output:** Use `console.print()` from the `rich` library. Use `[green]`, `[bold red]`, `[cyan]`, etc., for syntax coloring. Use `typer.prompt` and `typer.confirm` for interactivity.
- **Push/Pull Sync Logic:** 
  - **Pulling:** Fetch schemas first to see what objects exist in the org, then iterate over types to pull the JSON data, dumping `code` fields into local files.
  - **Pushing:** Iterate through the `object/` directory, comparing local file contents to the `*_metadata.json` state map. Send PATCH for changes and POST for new files.
import typer
import subprocess
import shutil
import os
import json
from pathlib import Path
from rich.console import Console

hermes_app = typer.Typer(help="Manage distributed Hermes Agentic Networks", no_args_is_help=True)
console = Console()

HERMES_HOME = Path.home() / ".hermes"
NETWORK_DIR = HERMES_HOME / ".valstorm-network"
PROFILES_DIR = HERMES_HOME / "profiles"
SOURCES_FILE = NETWORK_DIR / "sources.json"


def ensure_git():
    if not shutil.which("git"):
        console.print("[bold red]Error:[/bold red] Git is required but not installed.")
        raise typer.Exit(1)


def load_sources() -> dict:
    """Load the sources.json state file. Returns {"sources": {...}} (empty dict of sources if missing/corrupt)."""
    if not SOURCES_FILE.exists():
        return {"sources": {}}
    try:
        with open(SOURCES_FILE, "r") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "sources" not in data:
            return {"sources": {}}
        return data
    except (json.JSONDecodeError, OSError):
        return {"sources": {}}


def save_sources(data: dict) -> None:
    NETWORK_DIR.mkdir(parents=True, exist_ok=True)
    with open(SOURCES_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _derive_source_name(repo_url: str) -> str:
    """Derive a source slug from a repo URL's basename, stripping a trailing .git."""
    name = repo_url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[: -len(".git")]
    return name


def _migrate_legacy_single_source():
    """
    Backward-compat migration: if NETWORK_DIR/.git exists (old single-repo layout)
    but sources.json does not, move the existing clone into NETWORK_DIR/default/
    and register it as a source named 'default'.
    """
    if SOURCES_FILE.exists():
        return
    if not (NETWORK_DIR / ".git").exists():
        return

    console.print("[yellow]Detected legacy single-source network layout. Migrating to multi-source layout...[/yellow]")

    default_dir = NETWORK_DIR / "default"
    tmp_dir = NETWORK_DIR.parent / ".valstorm-network-migrate-tmp"

    # Best-effort: read the origin remote before we move anything.
    repo_url = ""
    try:
        res = subprocess.run(
            ["git", "-C", str(NETWORK_DIR), "remote", "get-url", "origin"],
            capture_output=True, text=True,
        )
        if res.returncode == 0:
            repo_url = res.stdout.strip()
    except OSError:
        pass

    # Move NETWORK_DIR itself (with all its content, including .git) to a temp
    # location, then recreate NETWORK_DIR fresh and move the temp dir into
    # NETWORK_DIR/default/.
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    shutil.move(str(NETWORK_DIR), str(tmp_dir))
    NETWORK_DIR.mkdir(parents=True, exist_ok=True)
    shutil.move(str(tmp_dir), str(default_dir))

    data = {"sources": {"default": {"repo_url": repo_url}}}
    save_sources(data)

    console.print(f"[green]Migrated legacy network into {default_dir}[/green]")
    console.print(
        "[yellow]Your existing profiles in ~/.hermes/profiles/* pointed at the old paths and are now stale. "
        "Run 'valstorm hermes sync' to update profiles at their new locations.[/yellow]"
    )


def run_hermes(profile, args, capture=True):
    """Subprocess wrapper for the `hermes` CLI, mirroring the standalone sync-profile-credentials script."""
    cmd = ["hermes"]
    if profile:
        cmd += ["-p", profile]
    cmd += args
    return subprocess.run(cmd, capture_output=capture, text=True)


def profile_dir(profile):
    """Resolve a profile's home directory via `hermes config path` (read-side inspection only)."""
    r = run_hermes(profile, ["config", "path"])
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f"Could not resolve config path for profile {profile!r}: {r.stderr.strip()}")
    return Path(r.stdout.strip()).parent


def _config_get(profile, key):
    r = run_hermes(profile, ["config", "get", key])
    if r.returncode != 0:
        return None
    value = r.stdout.strip()
    return value or None


def _config_set(profile, key, value):
    r = run_hermes(profile, ["config", "set", key, value])
    return r.returncode == 0, (r.stdout.strip() or r.stderr.strip())


def sync_model_config(source, target):
    """Backfill model.default/model.provider from source (default profile if None) into target.

    Additive-only: if `target` already has its own model configured — e.g. a
    newly-linked network profile whose config.example.yaml was just copied to
    config.yaml with an intentional model tier (see model.md) — that tier is
    left untouched. Only profiles with NO model configured at all (blank
    config, no example, or the source's model.default is empty) fall back to
    copying the source's model. Without this guard, every profile in an
    agentic network silently collapses onto whatever model the default
    profile happens to use, defeating tiered model allocation entirely.
    """
    existing_model = _config_get(target, "model.default")
    existing_provider = _config_get(target, "model.provider")
    if existing_model and existing_provider:
        return
    default_model = _config_get(source, "model.default")
    provider = _config_get(source, "model.provider")
    if not default_model or not provider:
        return
    for key, value in (("model.default", default_model), ("model.provider", provider)):
        _config_set(target, key, value)


def load_auth_pool(profile_dir_path):
    auth_file = profile_dir_path / "auth.json"
    if not auth_file.exists():
        return {}
    with auth_file.open() as f:
        return json.load(f)


def read_env_file(path):
    values = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    return values


def write_env_var(path, key, value):
    """Set key=value in an env file, replacing an existing line for that key."""
    existing = read_env_file(path)
    if existing.get(key) == value:
        return "unchanged"
    lines = path.read_text().splitlines() if path.exists() else []
    replaced = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}=") and not stripped.startswith("#"):
            new_lines.append(f"{key}={value}")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        new_lines.append(f"{key}={value}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(new_lines) + "\n")
    path.chmod(0o600)
    return "updated" if replaced else "added"


def sync_credentials(source, target, include_oauth=False):
    """Copy provider/env credentials from source (default profile if None) into target."""
    src_dir = profile_dir(source)
    tgt_dir = profile_dir(target)

    src_auth = load_auth_pool(src_dir)
    tgt_auth = load_auth_pool(tgt_dir)
    src_pool = src_auth.get("credential_pool", {})
    tgt_pool = tgt_auth.get("credential_pool", {})

    src_env = read_env_file(src_dir / ".env")
    tgt_env_path = tgt_dir / ".env"

    for provider, creds in src_pool.items():
        existing_tokens = {
            c.get("access_token") or c.get("api_key")
            for c in tgt_pool.get(provider, [])
        }
        for cred in creds:
            auth_type = cred.get("auth_type")
            source_tag = cred.get("source", "")
            label = cred.get("label", provider)

            if source_tag == "gh_cli" or (auth_type == "oauth" and not include_oauth):
                continue

            if source_tag.startswith("env:"):
                var_name = source_tag.split(":", 1)[1]
                value = src_env.get(var_name)
                if value is None:
                    continue
                write_env_var(tgt_env_path, var_name, value)
                continue

            token = cred.get("access_token") or cred.get("api_key")
            if not token or token in existing_tokens:
                continue
            cred_type = "oauth" if auth_type == "oauth" else "api-key"
            r = run_hermes(
                target,
                ["auth", "add", provider, "--type", cred_type, "--api-key", token, "--label", f"synced-from-{source or 'default'}"],
            )
            if r.returncode == 0:
                existing_tokens.add(token)


def _sync_default_credentials_into(target_profile_name):
    """Sync model config + credentials from the default profile into a newly-linked profile."""
    sync_model_config(None, target_profile_name)
    sync_credentials(None, target_profile_name, include_oauth=False)


def link_profiles():
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    data = load_sources()
    sources = data.get("sources", {})

    for source_name in sources:
        source_dir = NETWORK_DIR / source_name
        if not source_dir.is_dir():
            continue

        for item in source_dir.iterdir():
            if item.is_dir() and item.name != ".git":
                target = PROFILES_DIR / item.name

                if target.is_symlink():
                    target.unlink()
                    shutil.copytree(item, target)
                    console.print(f"  [green]Migrated {item.name} from symlink to copy[/green]")
                elif not target.exists():
                    shutil.copytree(item, target)
                    console.print(f"  [green]Copied {item.name}[/green]")
                else:
                    # Overwrite-copy updates existing files without touching local runtime files.
                    # Note: files removed from source repo are not deleted in target profile.
                    shutil.copytree(item, target, dirs_exist_ok=True)
                    console.print(f"  [dim]Updated {item.name}[/dim]")

                # Generate config.yaml from config.example.yaml FIRST — this
                # establishes the profile's own intended model tier (see
                # model.md) before credential sync runs. sync_model_config()
                # is additive-only (won't override an existing model), but
                # that guard only works if config.yaml — and therefore the
                # tiered model — already exists by the time it checks.
                config_example = target / "config.example.yaml"
                config = target / "config.yaml"
                if config_example.exists() and not config.exists():
                    try:
                        shutil.copy2(config_example, config)
                        console.print(f"  [dim]Generated default config.yaml for {item.name}[/dim]")
                    except OSError as e:
                        console.print(f"  [yellow]Warning:[/yellow] Failed to generate config.yaml for {item.name}: {e}")

                try:
                    _sync_default_credentials_into(item.name)
                except Exception as e:
                    console.print(f"  [yellow]Warning:[/yellow] Failed to sync credentials for {item.name}: {e}")


@hermes_app.command("install")
def install(
    repo_url: str = typer.Argument(..., help="The Git repository URL containing the agentic network"),
    name: str = typer.Option(None, "--name", help="Name for this source (defaults to the repo URL's basename)"),
):
    """Onboard a team's agentic network."""
    ensure_git()
    _migrate_legacy_single_source()

    source_name = name or _derive_source_name(repo_url)
    NETWORK_DIR.mkdir(parents=True, exist_ok=True)
    source_dir = NETWORK_DIR / source_name

    if source_dir.exists():
        if (source_dir / ".git").exists():
            console.print(
                f"[yellow]Source '{source_name}' already exists at {source_dir}. "
                "Use 'valstorm hermes sync' to update it.[/yellow]"
            )
            raise typer.Exit(1)
        else:
            console.print(
                f"[yellow]Warning:[/yellow] Source '{source_name}' exists but is missing/corrupt (no .git found). "
                "Re-cloning..."
            )
            shutil.rmtree(source_dir)

    console.print(f"Cloning {repo_url} into {source_dir}...")
    res = subprocess.run(["git", "clone", repo_url, str(source_dir)], capture_output=True, text=True)
    if res.returncode != 0:
        console.print(f"[bold red]Git clone failed:[/bold red]\n{res.stderr}")
        if source_dir.exists():
            shutil.rmtree(source_dir)
        raise typer.Exit(1)

    data = load_sources()
    data.setdefault("sources", {})[source_name] = {"repo_url": repo_url}
    save_sources(data)

    console.print("Copying profiles...")
    link_profiles()
    console.print("\n[bold green]Network installed successfully![/bold green]")
    console.print("Run `hermes --profile <profile_name>` to begin.")


@hermes_app.command("sync")
def sync():
    """Keep the team's agentic network up to date."""
    ensure_git()
    _migrate_legacy_single_source()

    data = load_sources()
    sources = data.get("sources", {})

    if not sources:
        console.print("[bold red]No sources installed. Run 'valstorm hermes install <repo-url>' first.[/bold red]")
        raise typer.Exit(1)

    any_failed = False
    for source_name in sources:
        source_dir = NETWORK_DIR / source_name
        if not (source_dir / ".git").exists():
            console.print(f"[yellow]Skipping '{source_name}':[/yellow] not found or missing .git at {source_dir}.")
            any_failed = True
            continue

        console.print(f"Pulling latest updates for '{source_name}'...")
        res = subprocess.run(["git", "-C", str(source_dir), "pull"], capture_output=True, text=True)
        if res.returncode != 0:
            console.print(f"[bold red]Git pull failed for '{source_name}':[/bold red]\n{res.stderr}")
            any_failed = True
            continue

        console.print(f"  [dim]{res.stdout.strip()}[/dim]")

    console.print("Updating profiles...")
    link_profiles()

    if any_failed:
        console.print("\n[yellow]Network synced with some errors (see above).[/yellow]")
    else:
        console.print("\n[bold green]Network synced successfully![/bold green]")

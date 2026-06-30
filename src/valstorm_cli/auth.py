import json
import os
import sys
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console

import httpx
console = Console()

def decode_jwt_payload(token: str) -> dict:
    import base64
    import json
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return {}
        payload_b64 = parts[1]
        padding = len(payload_b64) % 4
        if padding:
            payload_b64 += "=" * (4 - padding)
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_bytes.decode('utf-8'))
    except Exception:
        return {}

# Configuration
ENVIRONMENTS = {
    "prod": "https://api.valstorm.com",
    "dev": "https://api-dev.valstorm.com",
    "local": "http://localhost:8010"
}

WEB_ENVIRONMENTS = {
    "prod": "https://app.valstorm.com",
    "dev": "https://app-dev.valstorm.com",
    "local": "http://localhost:3000"
}

def _load_workspace_config() -> dict:
    """Helper to find and load valstorm.json by searching upwards."""
    current = Path.cwd()
    while current != current.parent:
        config_path = current / "valstorm.json"
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
            break
        current = current.parent
    return {}

def get_env() -> str:
    if "VALSTORM_ENV" in os.environ:
        return os.environ["VALSTORM_ENV"].lower()
    config = _load_workspace_config()
    return config.get("env", "prod").lower()

def get_profile() -> str:
    if "VALSTORM_PROFILE" in os.environ:
        return os.environ["VALSTORM_PROFILE"].lower()
    config = _load_workspace_config()
    return config.get("profile", "default").lower()

def get_sandbox() -> Optional[str]:
    config = _load_workspace_config()
    val = config.get("sandbox")
    return val.lower() if val else None

def get_base_url(env: str = None) -> str:
    env = env or get_env()
    return ENVIRONMENTS.get(env, ENVIRONMENTS["prod"])

def get_web_url(env: str = None) -> str:
    env = env or get_env()
    return WEB_ENVIRONMENTS.get(env, WEB_ENVIRONMENTS["prod"])

def get_api_base_url(env: str = None) -> str:
    return f"{get_base_url(env)}/v1"

def get_auth_file(env: str, profile: str) -> Path:
    """Helper to get the auth file path for a specific environment and profile."""
    auth_dir = Path.home() / ".valstorm"
    
    # 1. Try the new standard pattern: auth_{env}_{profile}.json
    new_path = auth_dir / f"auth_{env}_{profile}.json"
    if new_path.exists():
        return new_path
    
    # 2. Fallback for legacy pattern if profile is 'default': auth_{env}.json
    if profile == "default":
        legacy_path = auth_dir / f"auth_{env}.json"
        if legacy_path.exists():
            return legacy_path
            
    # 3. Default to the new pattern for new files
    return new_path


class ValstormAuth:
    _validation_cache = {} # (env, profile) -> bool

    def __init__(self, profile: str = None, env: str = None, use_parent: bool = False):
        self.profile = profile or get_profile()
        self.env = env or get_env()
        self.sandbox = None if use_parent else get_sandbox()
        self.access_token = None
        self.refresh_token = None
        self.organization_name = None
        self.default_app_id = None
        self._load_tokens()

    @property
    def auth_file(self) -> Path:
        return get_auth_file(self.env, self.profile)

    def _load_tokens(self):
        # Reset current tokens before loading
        self.access_token = None
        self.refresh_token = None
        self.organization_name = None
        self.default_app_id = None
        
        if self.auth_file.exists():
            try:
                content = self.auth_file.read_text().strip()
                if not content:
                    return
                data = json.loads(content)
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                self.organization_name = data.get("organization_name")
                self.default_app_id = data.get("default_app_id")

            except (json.JSONDecodeError, Exception):
                # If file is corrupted or unreadable, we ignore it 
                # so ensure_valid_token will return False and trigger a re-login
                pass

    def save_tokens(self, access_token: str, refresh_token: str = None, organization_name: str = None, default_app_id: str = None):
        if access_token:
            self.access_token = access_token
        if refresh_token is not None:
            self.refresh_token = refresh_token
        if organization_name is not None:
            self.organization_name = organization_name
        if default_app_id is not None:
            self.default_app_id = default_app_id
            
        try:
            self.auth_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "organization_name": self.organization_name,
                "default_app_id": self.default_app_id
            }

            # Write to a temporary file first then rename to ensure atomicity
            temp_file = self.auth_file.with_suffix(".tmp")
            temp_file.write_text(json.dumps(data, indent=2))
            temp_file.replace(self.auth_file)
        except Exception as e:
            print(f"Error saving tokens for profile {self.profile}: {e}", file=sys.stderr)


    def get_client(self) -> httpx.Client:
        """Returns a synchronous HTTPX client configured with auth headers."""
        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        return httpx.Client(base_url=get_api_base_url(self.env), headers=headers, timeout=10.0)

    def refresh_auth(self) -> bool:
        if not self.refresh_token:
            return False
        
        try:
            with httpx.Client(base_url=get_api_base_url(self.env), timeout=10.0) as client:
                response = client.post("/oauth2/refresh", json={"refresh_token": self.refresh_token})
                if response.status_code == 200:
                    data = response.json()
                    new_access = data.get("access_token")
                    new_refresh = data.get("refresh_token", self.refresh_token)
                    self.save_tokens(access_token=new_access, refresh_token=new_refresh)
                    return True
                else:
                    return False
        except Exception:
            # print(f"Error refreshing token: {e}", file=sys.stderr)
            return False

    def _get_cached_sandbox_token(self, sandbox_name: str) -> Optional[str]:
        if self.auth_file.exists():
            try:
                data = json.loads(self.auth_file.read_text())
                sandboxes = data.get("sandboxes", {})
                sandbox_data = sandboxes.get(sandbox_name, {})
                expires_at_str = sandbox_data.get("expires_at")
                if expires_at_str:
                    import datetime
                    expires_at = datetime.datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                    if datetime.datetime.now(datetime.timezone.utc) > expires_at:
                        return None
                return sandbox_data.get("access_token")
            except Exception:
                pass
        return None

    def _save_sandbox_token(self, sandbox_name: str, token: str):
        payload = decode_jwt_payload(token)
        expires_at = None
        if payload.get("exp"):
            import datetime
            expires_at = datetime.datetime.fromtimestamp(payload["exp"], datetime.timezone.utc).isoformat()
            
        try:
            self.auth_file.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            if self.auth_file.exists():
                try:
                    data = json.loads(self.auth_file.read_text())
                except Exception:
                    pass
            
            data["access_token"] = data.get("access_token", self.access_token)
            data["refresh_token"] = data.get("refresh_token", self.refresh_token)
            data["organization_name"] = data.get("organization_name", self.organization_name)
            data["default_app_id"] = data.get("default_app_id", self.default_app_id)
            
            if "sandboxes" not in data:
                data["sandboxes"] = {}
                
            data["sandboxes"][sandbox_name] = {
                "access_token": token,
                "expires_at": expires_at
            }
            
            temp_file = self.auth_file.with_suffix(".tmp")
            temp_file.write_text(json.dumps(data, indent=2))
            temp_file.replace(self.auth_file)
        except Exception as e:
            print(f"Error saving sandbox token: {e}", file=sys.stderr)

    def _validate_sandbox_token(self, token: str) -> bool:
        headers = {"Authorization": f"Bearer {token}"}
        try:
            with httpx.Client(base_url=get_api_base_url(self.env), headers=headers, timeout=5.0) as client:
                res = client.get("/auth/load")
                return res.status_code == 200
        except Exception:
            return False

    def _switch_to_sandbox_org(self, parent_token: str, sandbox_org_id: str) -> Optional[str]:
        headers = {"Authorization": f"Bearer {parent_token}"}
        try:
            with httpx.Client(base_url=get_api_base_url(self.env), headers=headers, timeout=10.0) as client:
                res = client.post("/switch", json={"id": sandbox_org_id})
                if res.status_code == 200:
                    return res.json().get("access_token")
                else:
                    console.print(f"[yellow]Switch organization failed ({res.status_code}): {res.text}[/yellow]")
        except Exception as e:
            console.print(f"[red]Error connecting to API to switch organization: {e}[/red]")
        return None

    def ensure_valid_token(self) -> bool:
        """Checks if the token is valid, attempting to refresh if it's not."""
        if self.sandbox:
            # 1. Validate parent token first
            parent_auth = ValstormAuth(profile=self.profile, env=self.env, use_parent=True)
            if not parent_auth.ensure_valid_token():
                return False
            
            # Since parent_auth may have refreshed the parent token, we reload our tokens
            self._load_tokens()
            parent_token = parent_auth.access_token
            if not parent_token:
                console.print("[red]Could not retrieve parent authentication token.[/red]")
                return False
            
            # 2. Get sandbox token
            parent_payload = decode_jwt_payload(parent_token)
            parent_org_id = parent_payload.get("org")
            if not parent_org_id:
                console.print("[red]Could not extract parent organization ID from authentication token.[/red]")
                return False
                
            sandbox_org_id = f"sandbox_{self.sandbox}_{parent_org_id}"
            
            cached_sandbox_token = self._get_cached_sandbox_token(self.sandbox)
            if cached_sandbox_token:
                if self._validate_sandbox_token(cached_sandbox_token):
                    self.access_token = cached_sandbox_token
                    return True
            
            console.print(f"Authenticating into sandbox [bold cyan]{self.sandbox}[/bold cyan]...")
            new_sandbox_token = self._switch_to_sandbox_org(parent_token, sandbox_org_id)
            if new_sandbox_token:
                self._save_sandbox_token(self.sandbox, new_sandbox_token)
                self.access_token = new_sandbox_token
                return True
            else:
                console.print(f"[red]Failed to authenticate into sandbox '{self.sandbox}'.[/red]")
                return False

        cache_key = (self.env, self.profile)
        if ValstormAuth._validation_cache.get(cache_key):
            console.print(f"[green]Token for profile '{self.profile}' in environment '{self.env}' is valid (cached).[/green]")
            return True

        if not self.access_token:
            console.print(f"[yellow]No access token found for profile '{self.profile}' in environment '{self.env}'. Please log in.[/yellow]")
            return False
            
        try:
            with self.get_client() as client:
                response = client.get("/auth/load")
                if response.status_code == 200:
                    user_data = response.json()
                    user = user_data.get("user", user_data)
                    if user.get("organization_name"):
                        self.save_tokens(access_token=self.access_token, organization_name=user.get("organization_name"))
                    
                    ValstormAuth._validation_cache[cache_key] = True
                    console.print(f"[green]Token for profile '{self.profile}' in environment '{self.env}' is valid.[/green]")
                    return True
                
                if response.status_code == 401:
                    success = self.refresh_auth()
                    if success:
                        ValstormAuth._validation_cache[cache_key] = True
                    console.print(f"[yellow]Access token for profile '{self.profile}' in environment '{self.env}' was invalid. {'Successfully refreshed.' if success else 'Failed to refresh, please log in again.'}[/yellow]")
                    return success
        except (httpx.ConnectError, httpx.ConnectTimeout):
            # If server is unreachable, we can't validate, but we don't want to spam error messages
            # Return False and let the command handle the failure
            console.print(f"[red]Unable to connect to Valstorm API at {get_api_base_url(self.env)} to validate token. Please check your network connection and try again.[/red]")
            return False
        except Exception:
            console.print(f"[red]An error occurred while validating the token for profile '{self.profile}' in environment '{self.env}'. Please try logging in again.[/red]")
            return False
        console.print(f"[red]Unexpected error validating token for profile '{self.profile}' in environment '{self.env}'. Please log in again.[/red]")
        return False


def find_project_root() -> Optional[Path]:
    current = Path.cwd()
    while current != current.parent:
        if (current / "valstorm.json").exists():
            return current
        current = current.parent
    return None

def get_project_root() -> Path:
    root = find_project_root()
    if root:
        return root
    raise typer.Exit(1)

def load_config(root: Path) -> dict:
    with open(root / "valstorm.json", "r") as f:
        return json.load(f)

def get_auth(profile: Optional[str] = None, env: Optional[str] = None, use_parent: bool = False) -> 'ValstormAuth':
    auth_profile = profile
    auth_env = env

    root = find_project_root()
    if root:
        try:
            config = load_config(root)
            if auth_profile is None:
                auth_profile = config.get("profile")
            if auth_env is None:
                auth_env = config.get("env")
        except Exception:
            pass

    return ValstormAuth(profile=auth_profile, env=auth_env, use_parent=use_parent)

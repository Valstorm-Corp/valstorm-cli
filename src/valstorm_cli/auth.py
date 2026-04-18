import json
import os
import sys
from pathlib import Path
from typing import Optional, Tuple
import httpx

# Configuration
ENVIRONMENTS = {
    "prod": "https://api.valstorm.com",
    "dev": "https://api-dev.valstorm.com",
    "local": "http://localhost:8010"
}

def get_env() -> str:
    return os.environ.get("VALSTORM_ENV", "prod").lower()

def get_profile() -> str:
    return os.environ.get("VALSTORM_PROFILE", "default").lower()

def get_base_url(env: str = None) -> str:
    env = env or get_env()
    return ENVIRONMENTS.get(env, ENVIRONMENTS["prod"])

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
    def __init__(self, profile: str = None, env: str = None):
        self.profile = profile or get_profile()
        self.env = env or get_env()
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
                data = json.loads(self.auth_file.read_text())
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                self.organization_name = data.get("organization_name")
                self.default_app_id = data.get("default_app_id")
            except Exception as e:
                print(f"Error loading tokens for profile {self.profile}: {e}", file=sys.stderr)

    def save_tokens(self, access_token: str, refresh_token: str = None, organization_name: str = None, default_app_id: str = None):
        self.access_token = access_token
        if refresh_token is not None:
            self.refresh_token = refresh_token
        if organization_name is not None:
            self.organization_name = organization_name
        if default_app_id is not None:
            self.default_app_id = default_app_id
            
        try:
            self.auth_file.parent.mkdir(parents=True, exist_ok=True)
            self.auth_file.write_text(json.dumps({
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "organization_name": self.organization_name,
                "default_app_id": self.default_app_id
            }, indent=2))
        except Exception as e:
            print(f"Error saving tokens for profile {self.profile}: {e}", file=sys.stderr)

    def get_client(self) -> httpx.Client:
        """Returns a synchronous HTTPX client configured with auth headers."""
        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        return httpx.Client(base_url=get_api_base_url(self.env), headers=headers)

    def refresh_auth(self) -> bool:
        if not self.refresh_token:
            return False
        
        try:
            with httpx.Client(base_url=get_api_base_url(self.env)) as client:
                response = client.post("/oauth2/refresh", json={"refresh_token": self.refresh_token})
                if response.status_code == 200:
                    data = response.json()
                    new_access = data.get("access_token")
                    new_refresh = data.get("refresh_token", self.refresh_token)
                    self.save_tokens(access_token=new_access, refresh_token=new_refresh)
                    return True
                else:
                    return False
        except Exception as e:
            print(f"Error refreshing token: {e}", file=sys.stderr)
            return False

    def ensure_valid_token(self) -> bool:
        """Checks if the token is valid, attempting to refresh if it's not."""
        if not self.access_token:
            return False
            
        with self.get_client() as client:
            response = client.get("/auth/load")
            if response.status_code == 200:
                user_data = response.json()
                if user_data.get("organization_name"):
                    self.save_tokens(access_token=self.access_token, organization_name=user_data.get("organization_name"))
                return True
            
            if response.status_code == 401:
                return self.refresh_auth()
                
        return False

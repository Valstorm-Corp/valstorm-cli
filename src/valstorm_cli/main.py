import typer
import httpx
from rich.console import Console
import getpass
from .auth import ValstormAuth, get_api_base_url

app = typer.Typer(help="Valstorm Developer CLI", no_args_is_help=True)
console = Console()

@app.command()
def status():
    """
    Check the status of the Valstorm API.
    """
    url = f"{get_api_base_url()}/status"
    console.print(f"Checking status for [blue]{url}[/blue]...")
    
    try:
        response = httpx.get(url, timeout=10.0)
        
        if response.status_code == 200:
            console.print(f"[bold green]SUCCESS:[/bold green] API is running and responded with HTTP 200.")
            console.print(response.json())
        else:
            console.print(f"[bold yellow]WARNING:[/bold yellow] API responded with status code {response.status_code}")
            console.print(response.text)
            
    except httpx.RequestError as e:
        console.print(f"[bold red]ERROR:[/bold red] Could not connect to the API. {e}")
    except Exception as e:
        console.print(f"[bold red]UNEXPECTED ERROR:[/bold red] {e}")

@app.command()
def login(
    profile: str = typer.Option("default", "--profile", "-p", help="Profile name to save these credentials under."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment (local, dev, prod).")
):
    """
    Authenticate with Valstorm.
    """
    auth = ValstormAuth(profile=profile, env=env)
    
    console.print(f"Logging in to [blue]{get_api_base_url(auth.env)}[/blue] (Profile: [cyan]{auth.profile}[/cyan])")
    
    email = typer.prompt("Email")
    password = typer.prompt("Password", hide_input=True)

    with httpx.Client(base_url=get_api_base_url(auth.env)) as client:
        # OAuth2 password flow uses form-urlencoded data
        response = client.post("/oauth2/login", data={
            "grant_type": "password",
            "username": email,
            "password": password
        })

        if response.status_code != 200:
            console.print(f"[bold red]Login Failed:[/bold red] {response.status_code}")
            console.print(response.text)
            raise typer.Exit(1)

        data = response.json()

        # Handle 2FA if required
        if "detail" in data and "2FA" in data["detail"]:
            console.print(f"[yellow]{data['detail']}[/yellow]")
            code = typer.prompt("Enter 2FA Code")
            
            verify_response = client.post("/oauth2/verify-2fa", json={
                "email": email,
                "code": code
            })
            
            if verify_response.status_code != 200:
                console.print(f"[bold red]2FA Verification Failed:[/bold red] {verify_response.text}")
                raise typer.Exit(1)
                
            data = verify_response.json()

        if "access_token" in data:
            auth.save_tokens(
                access_token=data["access_token"], 
                refresh_token=data.get("refresh_token")
            )
            console.print("[bold green]Successfully logged in![/bold green]")
        else:
            console.print("[bold red]Unexpected response during login.[/bold red]")
            console.print(data)

@app.command()
def whoami(
    profile: str = typer.Option("default", "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment.")
):
    """
    Display current authenticated user info.
    """
    auth = ValstormAuth(profile=profile, env=env)
    
    if not auth.ensure_valid_token():
        console.print("[bold red]Not logged in or token expired.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)
        
    with auth.get_client() as client:
        response = client.get("/auth/load")
        if response.status_code == 200:
            data = response.json()
            user = data.get("user", {})
            console.print(f"Logged in as: [bold cyan]{user.get('name', 'Unknown')}[/bold cyan]")
            console.print(f"Organization: [bold green]{user.get('organization_name', 'Unknown')}[/bold green]")
            console.print(f"Email: {user.get('email', 'Unknown')}")
            console.print(f"User ID: {user.get('id', 'Unknown')}")
            console.print(f"Org Id: {user.get('organization_id', 'Unknown')}")
            console.print(f"Role: {user.get('role', {}).get('name', 'Unknown')}")
        else:
            console.print(f"[bold red]Failed to load user data:[/bold red] {response.status_code}")

@app.callback()
def main():
    """
    Valstorm Developer CLI.
    """
    pass

if __name__ == "__main__":
    app()

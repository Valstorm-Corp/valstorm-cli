import typer
import httpx
from rich.console import Console

app = typer.Typer(help="Valstorm Developer CLI", no_args_is_help=True)
console = Console()

@app.command()
def status():
    """
    Check the status of the Valstorm API.
    """
    url = "https://api.valstorm.com/v1/status"
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

@app.callback()
def main():
    """
    Valstorm Developer CLI.
    """
    pass

if __name__ == "__main__":
    app()

"""Seabay CLI — seabay init | demo | doctor | status | inbox | task | listen."""

import json
import sys
from pathlib import Path

import click
import httpx

DEFAULT_API_URL = "http://localhost:8000/v1"


def _load_config() -> dict:
    """Load .seabay.json config file."""
    config_path = Path(".seabay.json")
    if not config_path.exists():
        click.echo("Error: .seabay.json not found. Run 'seabay init' first.", err=True)
        sys.exit(1)
    with open(config_path) as f:
        return json.load(f)


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config['api_key']}"}


@click.group()
@click.version_option(version="0.1.0", prog_name="seabay")
def cli():
    """Seabay CLI — manage your Seabay development environment."""
    pass


@cli.command()
@click.option("--slug", prompt="Agent slug", help="Unique agent identifier (lowercase, hyphens, underscores)")
@click.option("--name", prompt="Display name", help="Human-readable agent name")
@click.option("--type", "agent_type", type=click.Choice(["service", "personal"]), default="personal")
@click.option("--api-url", default=DEFAULT_API_URL, help="Seabay API URL")
def init(slug: str, name: str, agent_type: str, api_url: str):
    """Register a new agent and save credentials."""
    click.echo(f"Registering agent '{slug}' ({agent_type})...")

    try:
        resp = httpx.post(
            f"{api_url}/agents/register",
            json={"slug": slug, "display_name": name, "agent_type": agent_type},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        click.echo("\nAgent registered successfully!")
        click.echo(f"  ID:       {data['id']}")
        click.echo(f"  Slug:     {data['slug']}")
        click.echo(f"  API Key:  {data['api_key']}")
        click.echo("\nSave your API key — it will NOT be shown again.")

        config = {
            "agent_id": data["id"],
            "slug": data["slug"],
            "api_key": data["api_key"],
            "api_url": api_url,
        }
        with open(".seabay.json", "w") as f:
            json.dump(config, f, indent=2)
        click.echo("\nCredentials saved to .seabay.json")

    except httpx.HTTPStatusError as e:
        click.echo(f"Error: {e.response.text}", err=True)
        sys.exit(1)
    except httpx.ConnectError:
        click.echo(f"Error: Cannot connect to {api_url}. Is the server running?", err=True)
        sys.exit(1)


@cli.command()
def status():
    """Show current agent status and connection info."""
    config = _load_config()
    api_url = config.get("api_url", DEFAULT_API_URL)

    try:
        resp = httpx.get(
            f"{api_url}/agents/{config['agent_id']}",
            headers=_headers(config),
            timeout=10,
        )
        resp.raise_for_status()
        agent = resp.json()

        click.echo(f"\nAgent: {agent['display_name']} (@{agent['slug']})")
        click.echo(f"  ID:             {agent['id']}")
        click.echo(f"  Type:           {agent['agent_type']}")
        click.echo(f"  Status:         {agent['status']}")
        click.echo(f"  Verification:   {agent['verification_level']}")
        click.echo(f"  Visibility:     {agent['visibility_scope']}")
        click.echo(f"  Contact Policy: {agent['contact_policy']}")
        if agent.get('last_seen_at'):
            click.echo(f"  Last Seen:      {agent['last_seen_at']}")
        click.echo()

    except httpx.HTTPStatusError as e:
        click.echo(f"Error: {e.response.text}", err=True)
        sys.exit(1)
    except httpx.ConnectError:
        click.echo(f"Error: Cannot connect to {api_url}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--status", "task_status", default=None, help="Filter by status")
@click.option("--limit", default=20, help="Max items to return")
def inbox(task_status: str, limit: int):
    """Show task inbox."""
    config = _load_config()
    api_url = config.get("api_url", DEFAULT_API_URL)

    params = {"limit": str(limit)}
    if task_status:
        params["status"] = task_status

    try:
        resp = httpx.get(
            f"{api_url}/tasks/inbox",
            headers=_headers(config),
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json()

        tasks = result.get("data", [])
        if not tasks:
            click.echo("\nInbox is empty.")
            return

        click.echo(f"\nInbox ({len(tasks)} tasks):\n")
        for t in tasks:
            risk_badge = f" [{t['risk_level']}]" if t.get('risk_level', 'R0') != 'R0' else ""
            click.echo(f"  {t['id']}  {t['status']:20s}  {t['task_type']:15s}{risk_badge}")
            if t.get('description'):
                click.echo(f"    {t['description'][:80]}")

        if result.get("has_more"):
            click.echo(f"\n  ... more tasks available (cursor: {result['next_cursor']})")
        click.echo()

    except httpx.HTTPStatusError as e:
        click.echo(f"Error: {e.response.text}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("task_id")
@click.argument("action", type=click.Choice(["accept", "decline", "complete", "cancel"]))
@click.option("--reason", default=None, help="Reason (for decline/cancel)")
@click.option("--rating", default=None, type=float, help="Rating (for complete)")
def task(task_id: str, action: str, reason: str, rating: float):
    """Manage a task: accept, decline, complete, or cancel."""
    config = _load_config()
    api_url = config.get("api_url", DEFAULT_API_URL)

    body = {}
    if reason:
        body["reason"] = reason
    if rating is not None:
        body["rating"] = rating

    try:
        resp = httpx.post(
            f"{api_url}/tasks/{task_id}/{action}",
            headers=_headers(config),
            json=body,
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json()
        click.echo(f"\nTask {task_id}: {action} -> {result.get('status', 'done')}")

    except httpx.HTTPStatusError as e:
        click.echo(f"Error: {e.response.text}", err=True)
        sys.exit(1)


@cli.command()
def listen():
    """Listen for real-time events via SSE."""
    config = _load_config()
    api_url = config.get("api_url", DEFAULT_API_URL)

    click.echo("Connecting to event stream...")

    try:
        with httpx.stream(
            "GET",
            f"{api_url}/events/stream",
            headers={**_headers(config), "Accept": "text/event-stream"},
            timeout=None,
        ) as resp:
            resp.raise_for_status()
            click.echo("Connected. Listening for events (Ctrl+C to stop)...\n")

            event_type = None
            data_lines = []

            for line in resp.iter_lines():
                if line.startswith("event: "):
                    event_type = line[7:]
                elif line.startswith("data: "):
                    data_lines.append(line[6:])
                elif line == "" and event_type:
                    raw_data = "\n".join(data_lines)
                    if event_type == "heartbeat":
                        pass  # silent
                    else:
                        click.echo(f"[{event_type}] {raw_data}")
                    event_type = None
                    data_lines = []

    except KeyboardInterrupt:
        click.echo("\nDisconnected.")
    except httpx.ConnectError:
        click.echo(f"Error: Cannot connect to {api_url}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--api-url", default=DEFAULT_API_URL, help="Seabay API URL")
def demo(api_url: str):
    """Run a quick demo: register, search, create task."""
    click.echo("Running Seabay demo...\n")

    try:
        health = httpx.get(f"{api_url}/health", timeout=10).json()
        click.echo(f"Server: {health.get('service')} v{health.get('version')} ({health.get('region')})")

        svc = httpx.post(f"{api_url}/agents/register", json={
            "slug": "demo-svc",
            "display_name": "Demo Service",
            "agent_type": "service",
            "skills": ["translation", "writing"],
        }, timeout=30).json()
        click.echo(f"\nService agent: {svc['id']}")

        user = httpx.post(f"{api_url}/agents/register", json={
            "slug": "demo-user",
            "display_name": "Demo User",
            "agent_type": "personal",
        }, timeout=30).json()
        click.echo(f"User agent: {user['id']}")

        headers = {"Authorization": f"Bearer {user['api_key']}"}
        task_resp = httpx.post(f"{api_url}/tasks", json={
            "to_agent_id": svc["id"],
            "task_type": "service_request",
            "description": "Translate this document",
        }, headers=headers, timeout=30).json()
        click.echo(f"\nTask created: {task_resp['id']} (status: {task_resp['status']})")

        click.echo("\nDemo complete!")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--api-url", default=DEFAULT_API_URL, help="Seabay API URL")
def doctor(api_url: str):
    """Check Seabay development environment health."""
    checks = []

    try:
        resp = httpx.get(f"{api_url}/health", timeout=5)
        if resp.status_code == 200:
            checks.append(("API Server", "OK", resp.json().get("version", "unknown")))
        else:
            checks.append(("API Server", "ERROR", f"Status {resp.status_code}"))
    except httpx.ConnectError:
        checks.append(("API Server", "FAIL", f"Cannot connect to {api_url}"))

    try:
        with open(".seabay.json") as f:
            config = json.load(f)
        checks.append(("Local Config", "OK", f"Agent: {config.get('slug', 'unknown')}"))
    except FileNotFoundError:
        checks.append(("Local Config", "MISSING", "Run 'seabay init' first"))

    click.echo("\nSeabay Doctor\n")
    for name, check_status, detail in checks:
        icon = {"OK": "v", "ERROR": "x", "FAIL": "x", "MISSING": "?"}.get(check_status, "?")
        click.echo(f"  {icon} {name}: {check_status} — {detail}")
    click.echo()


if __name__ == "__main__":
    cli()

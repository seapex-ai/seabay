"""Terminal card rendering for Seabay Shell — renders cards and structured data with ANSI colors."""

from __future__ import annotations

from typing import Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.markdown import Markdown

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


# ANSI color codes as fallback
class _Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


class TerminalRenderer:
    """Renders Seabay cards, task info, and match results in the terminal."""

    def __init__(self, use_rich: bool = True):
        self.use_rich = use_rich and HAS_RICH
        if self.use_rich:
            self.console = Console()
        else:
            self.console = None

    def render_text(self, text: str) -> None:
        """Render plain text / markdown-ish response."""
        if self.use_rich:
            try:
                self.console.print(Markdown(text))
            except Exception:
                self.console.print(text)
        else:
            print(text)

    def render_agent(self, agent: dict) -> None:
        """Render an agent profile card."""
        if self.use_rich:
            self._rich_agent(agent)
        else:
            self._plain_agent(agent)

    def render_task(self, task: dict) -> None:
        """Render a task detail card."""
        if self.use_rich:
            self._rich_task(task)
        else:
            self._plain_task(task)

    def render_inbox(self, tasks: list[dict], has_more: bool = False) -> None:
        """Render inbox task list."""
        if self.use_rich:
            self._rich_inbox(tasks, has_more)
        else:
            self._plain_inbox(tasks, has_more)

    def render_match_results(self, results: list[dict], summary: str = "") -> None:
        """Render match/search results."""
        if self.use_rich:
            self._rich_matches(results, summary)
        else:
            self._plain_matches(results, summary)

    def render_task_approval(self, task: dict) -> None:
        """Render a task approval card with action hints."""
        if self.use_rich:
            self._rich_approval(task)
        else:
            self._plain_approval(task)

    def render_status(self, agent: dict, health: Optional[dict] = None) -> None:
        """Render connection status."""
        if self.use_rich:
            self._rich_status(agent, health)
        else:
            self._plain_status(agent, health)

    def render_error(self, message: str) -> None:
        """Render an error message."""
        if self.use_rich:
            self.console.print(f"[bold red]Error:[/bold red] {message}")
        else:
            print(f"{_Colors.RED}{_Colors.BOLD}Error:{_Colors.RESET} {message}")

    def render_success(self, message: str) -> None:
        """Render a success message."""
        if self.use_rich:
            self.console.print(f"[bold green]OK:[/bold green] {message}")
        else:
            print(f"{_Colors.GREEN}{_Colors.BOLD}OK:{_Colors.RESET} {message}")

    def render_info(self, message: str) -> None:
        """Render an informational message."""
        if self.use_rich:
            self.console.print(f"[dim]{message}[/dim]")
        else:
            print(f"{_Colors.DIM}{message}{_Colors.RESET}")

    def render_tool_call(self, name: str, args: dict) -> None:
        """Show a tool call being made (debug mode)."""
        if self.use_rich:
            self.console.print(f"  [dim cyan]-> {name}({args})[/dim cyan]")
        else:
            print(f"  {_Colors.CYAN}{_Colors.DIM}-> {name}({args}){_Colors.RESET}")

    # ── Rich rendering ──

    def _rich_agent(self, agent: dict) -> None:
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="bold cyan", width=18)
        table.add_column("Value")

        table.add_row("Name", agent.get("display_name", "Unknown"))
        table.add_row("Slug", f"@{agent.get('slug', '?')}")
        table.add_row("Type", agent.get("agent_type", "?"))
        table.add_row("Status", self._status_badge(agent.get("status", "offline")))
        table.add_row("Verification", agent.get("verification_level", "none"))

        profile = agent.get("profile") or {}
        if profile.get("skills"):
            table.add_row("Skills", ", ".join(profile["skills"]))
        if profile.get("languages"):
            table.add_row("Languages", ", ".join(profile["languages"]))
        if profile.get("bio"):
            table.add_row("Bio", profile["bio"])
        if profile.get("location_city"):
            loc = profile.get("location_city", "")
            if profile.get("location_country"):
                loc += f", {profile['location_country']}"
            table.add_row("Location", loc)

        self.console.print(Panel(table, title="Agent Profile", border_style="blue"))

    def _rich_task(self, task: dict) -> None:
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="bold cyan", width=18)
        table.add_column("Value")

        table.add_row("Task ID", task.get("id", "?"))
        table.add_row("Type", task.get("task_type", "?"))
        table.add_row("Status", self._status_badge(task.get("status", "?")))
        table.add_row("Risk Level", self._risk_badge(task.get("risk_level", "R0")))
        if task.get("description"):
            table.add_row("Description", task["description"])
        table.add_row("From", task.get("from_agent_id", "?"))
        table.add_row("To", task.get("to_agent_id", "?"))
        if task.get("created_at"):
            table.add_row("Created", task["created_at"])

        self.console.print(Panel(table, title="Task Details", border_style="yellow"))

    def _rich_inbox(self, tasks: list[dict], has_more: bool) -> None:
        if not tasks:
            self.console.print("[dim]Inbox is empty.[/dim]")
            return

        table = Table(title="Inbox", show_lines=False)
        table.add_column("ID", style="dim", max_width=12)
        table.add_column("Status", max_width=20)
        table.add_column("Type", max_width=15)
        table.add_column("Risk")
        table.add_column("Description", max_width=40)

        for t in tasks:
            table.add_row(
                t.get("id", "?")[:12],
                self._status_badge(t.get("status", "?")),
                t.get("task_type", "?"),
                self._risk_badge(t.get("risk_level", "R0")),
                (t.get("description") or "")[:40],
            )

        self.console.print(table)
        if has_more:
            self.console.print("[dim]... more tasks available[/dim]")

    def _rich_matches(self, results: list[dict], summary: str) -> None:
        if summary:
            self.console.print(f"\n{summary}\n")

        if not results:
            self.console.print("[dim]No matches found.[/dim]")
            return

        for i, r in enumerate(results, 1):
            table = Table(show_header=False, box=None, padding=(0, 1))
            table.add_column("Key", style="bold", width=16)
            table.add_column("Value")

            table.add_row("Name", r.get("display_name", "Unknown"))
            table.add_row("Agent Ref", r.get("agent_ref", r.get("agent_id", "?")))
            if r.get("skills"):
                table.add_row("Skills", ", ".join(r["skills"]))
            if r.get("location"):
                table.add_row("Location", r["location"])
            if r.get("verification"):
                table.add_row("Verified", r["verification"])
            if r.get("last_active"):
                table.add_row("Last Active", r["last_active"])
            if r.get("success_rate_30d") is not None:
                table.add_row("Success Rate", f"{r['success_rate_30d']:.0%}")
            if r.get("why_matched"):
                for reason in r["why_matched"]:
                    table.add_row("", f"  - {reason}")
            if r.get("match_score") is not None:
                table.add_row("Score", f"{r['match_score']:.1f}")
            if r.get("reasons"):
                for reason in r["reasons"]:
                    table.add_row("", f"  - {reason}")

            self.console.print(Panel(table, title=f"Match #{i}", border_style="green"))

    def _rich_approval(self, task: dict) -> None:
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="bold cyan", width=18)
        table.add_column("Value")

        table.add_row("Task ID", task.get("id", "?"))
        table.add_row("Type", task.get("task_type", "?"))
        table.add_row("Risk Level", self._risk_badge(task.get("risk_level", "R0")))
        if task.get("description"):
            table.add_row("Description", task["description"])
        table.add_row("From", task.get("from_agent_id", "?"))

        panel_content = table
        self.console.print(Panel(panel_content, title="Task Approval Required", border_style="red"))
        self.console.print("  [bold green]/accept[/bold green] <id>  — Accept this task")
        self.console.print("  [bold red]/decline[/bold red] <id>  — Decline this task")

    def _rich_status(self, agent: dict, health: Optional[dict]) -> None:
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="bold cyan", width=18)
        table.add_column("Value")

        table.add_row("Agent", agent.get("display_name", "Unknown"))
        table.add_row("Slug", f"@{agent.get('slug', '?')}")
        table.add_row("Type", agent.get("agent_type", "?"))
        table.add_row("Status", self._status_badge(agent.get("status", "offline")))
        table.add_row("Verification", agent.get("verification_level", "none"))

        if health:
            table.add_row("Server", f"{health.get('service', '?')} v{health.get('version', '?')}")
            table.add_row("Region", health.get("region", "?"))

        self.console.print(Panel(table, title="Seabay Status", border_style="blue"))

    def _status_badge(self, status: str) -> str:
        color_map = {
            "online": "green",
            "offline": "dim",
            "busy": "yellow",
            "pending_accept": "yellow",
            "pending_delivery": "yellow",
            "delivered": "yellow",
            "accepted": "blue",
            "in_progress": "blue",
            "waiting_human_confirm": "yellow",
            "completed": "green",
            "failed": "red",
            "declined": "red",
            "cancelled": "dim",
            "expired": "dim",
        }
        color = color_map.get(status, "white")
        return f"[{color}]{status}[/{color}]"

    def _risk_badge(self, level: str) -> str:
        color_map = {"R0": "green", "R1": "yellow", "R2": "red", "R3": "bold red"}
        color = color_map.get(level, "white")
        return f"[{color}]{level}[/{color}]"

    # ── Plain text fallback rendering ──

    def _plain_agent(self, agent: dict) -> None:
        print(f"\n{'=' * 50}")
        print("  Agent Profile")
        print(f"{'=' * 50}")
        print(f"  Name:         {agent.get('display_name', 'Unknown')}")
        print(f"  Slug:         @{agent.get('slug', '?')}")
        print(f"  Type:         {agent.get('agent_type', '?')}")
        print(f"  Status:       {agent.get('status', 'offline')}")
        print(f"  Verification: {agent.get('verification_level', 'none')}")
        profile = agent.get("profile") or {}
        if profile.get("skills"):
            print(f"  Skills:       {', '.join(profile['skills'])}")
        if profile.get("languages"):
            print(f"  Languages:    {', '.join(profile['languages'])}")
        if profile.get("bio"):
            print(f"  Bio:          {profile['bio']}")
        print(f"{'=' * 50}\n")

    def _plain_task(self, task: dict) -> None:
        print(f"\n{'=' * 50}")
        print("  Task Details")
        print(f"{'=' * 50}")
        print(f"  ID:          {task.get('id', '?')}")
        print(f"  Type:        {task.get('task_type', '?')}")
        print(f"  Status:      {task.get('status', '?')}")
        print(f"  Risk:        {task.get('risk_level', 'R0')}")
        if task.get("description"):
            print(f"  Description: {task['description']}")
        print(f"  From:        {task.get('from_agent_id', '?')}")
        print(f"  To:          {task.get('to_agent_id', '?')}")
        print(f"{'=' * 50}\n")

    def _plain_inbox(self, tasks: list[dict], has_more: bool) -> None:
        if not tasks:
            print("\nInbox is empty.\n")
            return
        print(f"\nInbox ({len(tasks)} tasks):\n")
        for t in tasks:
            risk = f" [{t.get('risk_level', 'R0')}]" if t.get("risk_level", "R0") != "R0" else ""
            print(f"  {t.get('id', '?')[:12]}  {t.get('status', '?'):20s}  {t.get('task_type', '?'):15s}{risk}")
            if t.get("description"):
                print(f"    {t['description'][:80]}")
        if has_more:
            print("\n  ... more tasks available")
        print()

    def _plain_matches(self, results: list[dict], summary: str) -> None:
        if summary:
            print(f"\n{summary}\n")
        if not results:
            print("No matches found.\n")
            return
        for i, r in enumerate(results, 1):
            print(f"\n--- Match #{i} ---")
            print(f"  Name:     {r.get('display_name', 'Unknown')}")
            print(f"  Ref:      {r.get('agent_ref', r.get('agent_id', '?'))}")
            if r.get("skills"):
                print(f"  Skills:   {', '.join(r['skills'])}")
            if r.get("why_matched"):
                for reason in r["why_matched"]:
                    print(f"    - {reason}")
            if r.get("reasons"):
                for reason in r["reasons"]:
                    print(f"    - {reason}")
        print()

    def _plain_approval(self, task: dict) -> None:
        print(f"\n{'=' * 50}")
        print("  TASK APPROVAL REQUIRED")
        print(f"{'=' * 50}")
        print(f"  Task ID:     {task.get('id', '?')}")
        print(f"  Type:        {task.get('task_type', '?')}")
        print(f"  Risk:        {task.get('risk_level', 'R0')}")
        if task.get("description"):
            print(f"  Description: {task['description']}")
        print(f"\n  /accept {task.get('id', '<id>')}  — Accept this task")
        print(f"  /decline {task.get('id', '<id>')} — Decline this task")
        print(f"{'=' * 50}\n")

    def _plain_status(self, agent: dict, health: Optional[dict]) -> None:
        print(f"\n{'=' * 50}")
        print("  Seabay Status")
        print(f"{'=' * 50}")
        print(f"  Agent:        {agent.get('display_name', 'Unknown')}")
        print(f"  Slug:         @{agent.get('slug', '?')}")
        print(f"  Status:       {agent.get('status', 'offline')}")
        if health:
            print(f"  Server:       {health.get('service', '?')} v{health.get('version', '?')}")
        print(f"{'=' * 50}\n")

"""EmbedAI Validator – CLI entry point."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from utils.logger import configure_logging
from utils.paths import ensure_output_dir, timestamped_path, PROJECT_ROOT

app = typer.Typer(
    name="embedai",
    help="EmbedAI Validator – extensible embedded hardware validation platform.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

@app.command()
def validate(
    board: Path = typer.Option(
        ..., "--board", "-b", help="Path to board profile YAML.", show_default=False
    ),
    mock: bool = typer.Option(False, "--mock", help="Run in mock/simulation mode."),
    suite: Optional[str] = typer.Option(
        None, "--suite", "-s", help="Run only plugins tagged with SUITE (e.g. smoke)."
    ),
    output_dir: Path = typer.Option(
        Path("output"), "--output", "-o", help="Directory for report artifacts."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
) -> None:
    """Run a full board validation and generate JSON + HTML reports."""
    log_file = ensure_output_dir() / "embedai.log"
    configure_logging(verbose=verbose, log_file=log_file)

    from core.orchestrator import Orchestrator
    from reports.json_export import export_json
    from reports.html_export import export_html

    console.rule("[bold cyan]EmbedAI Validator[/bold cyan]")

    orch = Orchestrator(
        board_path=board,
        mock_mode=mock,
        suite=suite,
        output_dir=output_dir,
    )

    try:
        run_result = orch.run()
    except Exception as exc:
        console.print(f"[bold red]Fatal error:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    # Export reports
    json_path = export_json(run_result)
    html_path = export_html(run_result)

    # Print summary table
    _print_summary(run_result)

    console.print()
    console.print(f"[dim]JSON:[/dim] {json_path}")
    console.print(f"[dim]HTML:[/dim] {html_path}")

    # Exit code reflects overall status
    if run_result.summary.overall_status.value in ("FAIL", "ERROR"):
        raise typer.Exit(code=2)


# ---------------------------------------------------------------------------
# inventory
# ---------------------------------------------------------------------------

@app.command()
def inventory(
    board: Path = typer.Option(
        ..., "--board", "-b", help="Path to board profile YAML.", show_default=False
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Collect and display host environment inventory for a board."""
    configure_logging(verbose=verbose)

    from board.loader import load_board
    from board.inventory import collect_environment

    profile = load_board(board)
    env = collect_environment()

    table = Table(title=f"Inventory – {profile.board.name}", show_lines=True)
    table.add_column("Key", style="cyan")
    table.add_column("Value")
    for k, v in env.items():
        table.add_row(k, v)
    console.print(table)


# ---------------------------------------------------------------------------
# report  (re-render from existing JSON)
# ---------------------------------------------------------------------------

@app.command()
def report(
    input_file: Path = typer.Option(
        ..., "--input", "-i", help="Path to existing JSON run result.", show_default=False
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Generate an HTML report from an existing JSON result file."""
    configure_logging(verbose=verbose)

    from core.result_model import RunResult
    from reports.html_export import export_html

    if not input_file.exists():
        console.print(f"[red]File not found:[/red] {input_file}")
        raise typer.Exit(code=1)

    run_result = RunResult.model_validate(json.loads(input_file.read_text()))
    html_path = export_html(run_result)
    console.print(f"HTML report saved → [cyan]{html_path}[/cyan]")


# ---------------------------------------------------------------------------
# plugins
# ---------------------------------------------------------------------------

@app.command(name="plugins")
def list_plugins() -> None:
    """List all registered plugins."""
    configure_logging()

    from plugins.base import load_all_plugins, get_registry
    load_all_plugins()

    registry = get_registry()
    table = Table(title="Registered Plugins", show_lines=True)
    table.add_column("Name", style="cyan")
    table.add_column("Type")
    table.add_column("Suites")
    table.add_column("Description")

    for name, cls in sorted(registry.items()):
        table.add_row(
            name,
            cls.test_type,
            ", ".join(cls.suites),
            cls.description,
        )
    console.print(table)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_summary(run_result) -> None:
    from core.result_model import Status

    table = Table(title=f"Results – {run_result.board_name}", show_lines=True)
    table.add_column("Test ID", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Message")
    table.add_column("ms", justify="right")

    status_style = {
        Status.PASS: "green",
        Status.FAIL: "red",
        Status.SKIP: "yellow",
        Status.ERROR: "magenta",
    }

    for r in run_result.results:
        style = status_style.get(r.status, "white")
        table.add_row(
            r.test_id,
            f"[{style}]{r.status.value}[/{style}]",
            r.message[:80],
            f"{r.duration_ms:.1f}",
        )

    console.print(table)

    s = run_result.summary
    overall_style = "green" if s.overall_status.value == "PASS" else "red"
    console.print(
        f"\nOverall: [{overall_style}]{s.overall_status.value}[/{overall_style}]  "
        f"PASS={s.passed} FAIL={s.failed} SKIP={s.skipped} ERROR={s.errors}"
    )


# ---------------------------------------------------------------------------

def main() -> None:
    app()


if __name__ == "__main__":
    main()

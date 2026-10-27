"""
show_training_task_result.py

Reads and displays:
1. Coordinator Start-Training Task Lifecycle duration & stage report (training_lifecycle_metrics.json).
2. Distributed Training Engine convergence metrics & loss progression (training_metrics.json).
3. Resilient fallback: gracefully handles missing reports with informative notices.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# UTF-8 console output guard for Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console()


def format_duration(seconds: float) -> str:
    """Format seconds into human-readable duration."""
    if seconds < 0.001:
        return f"{seconds * 1000:.1f}ms"
    if seconds < 60:
        return f"{seconds:.2f}s"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{int(minutes)}m {sec:04.1f}s ({seconds:.1f}s total)"
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours)}h {int(minutes)}m {sec:02.0f}s ({seconds:.1f}s total)"


def resolve_report_paths(
    custom_metrics: Optional[str] = None,
    custom_lifecycle: Optional[str] = None,
) -> Tuple[Optional[Path], Optional[Path]]:
    """
    Resolves paths for training_metrics.json and training_lifecycle_metrics.json.
    Searches CLI args first, then candidate directories: ./, ./work/, ./single_node_finetuning/.
    """
    metrics_path: Optional[Path] = None
    lifecycle_path: Optional[Path] = None

    if custom_metrics:
        p = Path(custom_metrics)
        if p.is_dir():
            p = p / "training_metrics.json"
        if p.is_file():
            metrics_path = p

    if custom_lifecycle:
        p = Path(custom_lifecycle)
        if p.is_dir():
            p = p / "training_lifecycle_metrics.json"
        if p.is_file():
            lifecycle_path = p

    search_dirs = [
        Path("."),
        Path("./work"),
        Path("./single_node_finetuning"),
    ]

    if metrics_path is None:
        for d in search_dirs:
            candidate = d / "training_metrics.json"
            if candidate.is_file():
                metrics_path = candidate
                break

    if lifecycle_path is None:
        for d in search_dirs:
            candidate = d / "training_lifecycle_metrics.json"
            if candidate.is_file():
                lifecycle_path = candidate
                break

    return metrics_path, lifecycle_path


def render_lifecycle_report(data: Dict[str, Any], file_path: Path) -> None:
    """Renders formatted tables and panels for the task lifecycle report."""
    meta = data.get("task_metadata", {})
    steps = data.get("steps", [])
    total_time = meta.get("total_elapsed_sec", 0.0) or 0.0

    status = meta.get("status", "UNKNOWN")
    status_style = "bold green" if status == "COMPLETED" else "bold red"

    meta_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    meta_table.add_column("Key", style="bold cyan")
    meta_table.add_column("Value", style="white")

    meta_table.add_row("Client Node ID", meta.get("client_node_id", "N/A"))
    meta_table.add_row("Model ID & Version", f"{meta.get('model_id', 'N/A')} (v{meta.get('model_version', 'N/A')})")
    meta_table.add_row("Dataset & Shard", f"{meta.get('data_set_id', 'N/A')} (Shard {meta.get('shard_id', 'N/A')})")
    meta_table.add_row("Lifecycle Status", f"[{status_style}]{status}[/{status_style}]")
    meta_table.add_row("Total Lifecycle Duration", format_duration(total_time))
    meta_table.add_row("Execution Timeline", f"{meta.get('start_time', 'N/A')}  -->  {meta.get('end_time', 'N/A')}")
    if meta.get("error"):
        meta_table.add_row("Failure Reason", f"[bold red]{meta.get('error')}[/bold red]")

    console.print(
        Panel(
            meta_table,
            title="[bold cyan]1. Coordinator Task Execution Overview[/bold cyan]",
            subtitle=f"[dim]Source: {file_path}[/dim]",
            box=box.ROUNDED,
            border_style="cyan",
        )
    )
    console.print()

    stages_table = Table(
        title="[bold magenta]Task Lifecycle Stage Breakdown (Execution Durations)[/bold magenta]",
        box=box.ROUNDED,
        header_style="bold magenta",
    )
    stages_table.add_column("#", style="dim", justify="right")
    stages_table.add_column("Stage Name", style="bold white")
    stages_table.add_column("Status", justify="center")
    stages_table.add_column("Duration", justify="right", style="cyan")
    stages_table.add_column("% Total", justify="right", style="yellow")
    stages_table.add_column("Stage Details / Assets", style="dim")

    for s in steps:
        step_num = str(s.get("step_number", ""))
        name = s.get("name", "")
        step_status = s.get("status", "UNKNOWN")
        st_style = "green" if step_status == "COMPLETED" else ("red" if step_status == "FAILED" else "yellow")
        status_str = f"[{st_style}]{step_status}[/{st_style}]"

        dur = s.get("duration_sec", 0.0)
        pct = (dur / total_time * 100.0) if total_time > 0 else 0.0

        details_dict = s.get("details", {}) or {}
        details_str = ", ".join(f"{k}={v}" for k, v in details_dict.items()) if details_dict else ""
        if s.get("error"):
            details_str = f"[red]ERROR: {s.get('error')}[/red]"

        stages_table.add_row(
            step_num,
            name,
            status_str,
            format_duration(dur),
            f"{pct:5.1f}%",
            details_str or "-",
        )

    console.print(stages_table)
    console.print()


def render_training_metrics_report(file_path: Path) -> None:
    """Invokes show_single_node_train_result to render training metrics and charts."""
    try:
        # Import and invoke the reference viewer directly
        test_dir = Path(__file__).resolve().parent
        if str(test_dir) not in sys.path:
            sys.path.insert(0, str(test_dir))

        import show_single_node_train_result
        show_single_node_train_result.main(metrics_path_arg=str(file_path))
    except Exception as e:
        console.print(f"[bold red]Failed to render training metrics via reference viewer:[/bold red] {e}")


def main() -> None:
    console.print()
    console.print(
        Panel.fit(
            "[bold white]TrainSwarm Distributed Training Task & Metrics Dashboard[/bold white]\n"
            "[dim]Integrated Coordinator Task Lifecycle Duration & Model Convergence Inspection[/dim]",
            border_style="magenta",
            box=box.DOUBLE,
        )
    )
    console.print()

    arg1 = sys.argv[1] if len(sys.argv) > 1 else None
    arg2 = sys.argv[2] if len(sys.argv) > 2 else None

    # Handle named or positional args
    custom_metrics = None
    custom_lifecycle = None
    if arg1 and arg1.endswith("training_lifecycle_metrics.json"):
        custom_lifecycle = arg1
    elif arg1:
        custom_metrics = arg1

    if arg2 and arg2.endswith("training_lifecycle_metrics.json"):
        custom_lifecycle = arg2
    elif arg2:
        custom_metrics = arg2

    metrics_path, lifecycle_path = resolve_report_paths(
        custom_metrics=custom_metrics,
        custom_lifecycle=custom_lifecycle,
    )

    # 1. Neither report found
    if metrics_path is None and lifecycle_path is None:
        console.print(
            Panel(
                "[bold yellow]No training report files found.[/bold yellow]\n\n"
                "Searched candidate locations:\n"
                " - [dim]./training_metrics.json[/dim] and [dim]./training_lifecycle_metrics.json[/dim]\n"
                " - [dim]./work/training_metrics.json[/dim] and [dim]./work/training_lifecycle_metrics.json[/dim]\n"
                " - [dim]./single_node_finetuning/training_metrics.json[/dim]\n\n"
                "Please run a training session or coordinator command first to generate JSON reports.\n"
                "Usage: [cyan]python show_training_task_result.py [METRICS_PATH] [LIFECYCLE_PATH][/cyan]",
                title="[yellow]Reports Not Found[/yellow]",
                box=box.ROUNDED,
                border_style="yellow",
            )
        )
        return

    # 2. Render Lifecycle Report if present
    if lifecycle_path and lifecycle_path.is_file():
        try:
            with open(lifecycle_path, "r", encoding="utf-8") as f:
                lifecycle_data = json.load(f)
            render_lifecycle_report(lifecycle_data, lifecycle_path)
        except Exception as e:
            console.print(f"[bold red]Failed to load lifecycle report '{lifecycle_path}':[/bold red] {e}\n")
    else:
        console.print(
            Panel(
                "[yellow]Notice: Task lifecycle metrics file ('training_lifecycle_metrics.json') was not found.[/yellow]\n"
                "[dim]Displaying training metrics report only.[/dim]",
                box=box.ROUNDED,
                border_style="yellow",
            )
        )
        console.print()

    # 3. Render Training Metrics Report if present
    if metrics_path and metrics_path.is_file():
        render_training_metrics_report(metrics_path)
    else:
        console.print(
            Panel(
                "[yellow]Notice: Model training metrics file ('training_metrics.json') was not found.[/yellow]\n"
                "[dim]Displaying task lifecycle duration report only.[/dim]",
                box=box.ROUNDED,
                border_style="yellow",
            )
        )
        console.print()


if __name__ == "__main__":
    main()

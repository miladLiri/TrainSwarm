"""
show_reports.py

Comprehensive Visual Reporting Dashboard & Progression Plotter for TinyStories:
1. Ingests evaluation, timing, and coordinator JSON telemetry from reports/.
2. Renders styled Rich terminal tables for model quality, cluster time spans, and audit metrics.
3. Renders inline ASCII/Unicode progression charts directly in terminal panels.
4. Generates a multi-panel high-resolution progression plot (reports/training_progression_plot.png).
Runs without command-line arguments.
"""

from __future__ import annotations
import json
import math
import os
from pathlib import Path
import sys

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# UTF-8 console output guard for Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console()

SAMPLE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = SAMPLE_DIR / "reports"
EVAL_PATH = REPORTS_DIR / "version_evaluations.json"
TIMINGS_PATH = REPORTS_DIR / "round_timings.json"
COORD_PATH = REPORTS_DIR / "coordinator_summary.json"
PLOT_PATH = REPORTS_DIR / "training_progression_plot.png"


def load_json_file(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        console.print(f"[yellow]Warning loading {path.name}: {e}[/yellow]")
        return None


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m}m {s:04.1f}s"


def render_header() -> None:
    title = Text("TrainSwarm: TinyStories Distributed Training Report", style="bold cyan")
    sub = Text("Semi-Distributed Federated Learning Telemetry & Cross-Version Quality Evaluation", style="dim")
    console.print(Panel(Text.assemble(title, "\n", sub), box=box.ROUNDED, expand=False))


def render_evaluations_table(eval_data: dict | None) -> None:
    if not eval_data or "versions" not in eval_data:
        console.print("[yellow][!] No model evaluation metrics found in reports/version_evaluations.json[/yellow]")
        console.print("[dim]Run `python verify.py` to evaluate model versions.[/dim]\n")
        return

    table = Table(
        title="Model Quality & Convergence Progression",
        box=box.ROUNDED,
        header_style="bold magenta",
        show_lines=True,
    )
    table.add_column("Version", style="bold cyan", justify="center")
    table.add_column("Loss", justify="right")
    table.add_column("Loss Delta", justify="right")
    table.add_column("Perplexity", justify="right")
    table.add_column("PPL Delta", justify="right")
    table.add_column("Accuracy (Top-1)", justify="right")
    table.add_column("Acc Delta", justify="right")
    table.add_column("Status", justify="center")

    versions = eval_data.get("versions", [])
    for v in versions:
        v_num = v["version"]
        v_str = f"v{v_num}" + (" (Base)" if v.get("is_baseline") else "")

        loss_str = f"{v['loss']:.4f}"
        loss_d = v.get("loss_delta_percent")
        loss_d_str = f"{loss_d:+.2f}%" if loss_d is not None else "-"
        loss_style = "green" if loss_d and loss_d < 0 else "dim"

        ppl_str = f"{v['perplexity']:.2f}"
        ppl_d = v.get("perplexity_delta_percent")
        ppl_d_str = f"{ppl_d:+.2f}%" if ppl_d is not None else "-"
        ppl_style = "green" if ppl_d and ppl_d < 0 else "dim"

        acc_str = f"{v['top1_accuracy'] * 100:.2f}%"
        acc_d = v.get("accuracy_delta_percent")
        acc_d_str = f"{acc_d:+.2f}%" if acc_d is not None else "-"
        acc_style = "green" if acc_d and acc_d > 0 else "dim"

        status_str = "[cyan]Baseline[/cyan]" if v.get("is_baseline") else "[bold green]Aggregated[/bold green]"

        table.add_row(
            v_str,
            loss_str,
            Text(loss_d_str, style=loss_style),
            ppl_str,
            Text(ppl_d_str, style=ppl_style),
            acc_str,
            Text(acc_d_str, style=acc_style),
            status_str,
        )

    console.print(table)
    console.print()


def render_ascii_charts(eval_data: dict | None) -> None:
    """Renders terminal ASCII trend charts for Perplexity and Accuracy."""
    if not eval_data or "versions" not in eval_data or len(eval_data["versions"]) < 2:
        return

    versions = eval_data["versions"]
    v_labels = [f"v{v['version']}" for v in versions]
    accuracies = [v["top1_accuracy"] * 100 for v in versions]
    perplexities = [v["perplexity"] for v in versions]

    # Terminal ASCII Bar Graph for Accuracy
    acc_lines = []
    min_acc = min(accuracies)
    max_acc = max(accuracies)
    range_acc = max(max_acc - min_acc, 0.1)

    for v_lbl, acc in zip(v_labels, accuracies):
        bar_len = int(((acc - min_acc) / range_acc) * 25) + 3
        bar = "█" * bar_len
        acc_lines.append(f"  {v_lbl:>4} │ {bar} {acc:.2f}%")

    # Terminal ASCII Bar Graph for Perplexity
    ppl_lines = []
    min_ppl = min(perplexities)
    max_ppl = max(perplexities)
    range_ppl = max(max_ppl - min_ppl, 0.1)

    for v_lbl, ppl in zip(v_labels, perplexities):
        # Inverted bar: higher is worse, lower is better
        bar_len = int(((max_ppl - ppl) / range_ppl) * 25) + 3
        bar = "█" * bar_len
        ppl_lines.append(f"  {v_lbl:>4} │ {bar} {ppl:.2f} (lower is better)")

    chart_text = Text()
    chart_text.append("Top-1 Token Prediction Accuracy Progression:\n", style="bold green")
    chart_text.append("\n".join(acc_lines) + "\n\n")
    chart_text.append("Perplexity Reduction Progression (Convergence):\n", style="bold cyan")
    chart_text.append("\n".join(ppl_lines))

    console.print(Panel(chart_text, title="Terminal Progression Trends", box=box.ROUNDED, expand=False))
    console.print()


def render_timings_table(timings_data: dict | None) -> None:
    if not timings_data or "rounds" not in timings_data:
        console.print("[yellow][!] No round timing metrics found in reports/round_timings.json[/yellow]\n")
        return

    table = Table(
        title=f"Training Execution Spans & Cluster Throughput (Total: {timings_data.get('total_elapsed_seconds', 0):.1f}s)",
        box=box.ROUNDED,
        header_style="bold green",
        show_lines=True,
    )
    table.add_column("Round", style="bold cyan", justify="center")
    table.add_column("Base -> Target", justify="center")
    table.add_column("Elapsed", justify="right", style="bold yellow")
    table.add_column("Sharding", justify="right")
    table.add_column("Training", justify="right")
    table.add_column("Aggregation", justify="right")
    table.add_column("Shards", justify="center")

    for r in timings_data.get("rounds", []):
        r_num = str(r["round"])
        ver_span = f"v{r['base_model_version']} → v{r['produced_model_version']}"
        elap = format_duration(r["elapsed_seconds"])
        phases = r.get("phases", {})
        sharding = f"{phases.get('sharding_duration_seconds', 0):.1f}s"
        training = f"{phases.get('training_duration_seconds', 0):.1f}s"
        aggregation = f"{phases.get('aggregation_duration_seconds', 0):.1f}s"
        shards = str(r.get("shards_completed", 2))

        table.add_row(r_num, ver_span, elap, sharding, training, aggregation, shards)

    console.print(table)
    console.print()


def render_coordinator_table(coord_data: dict | None) -> None:
    if not coord_data or "rounds" not in coord_data:
        return

    table = Table(
        title="Coordinator Task Lifecycle & Node Assignments Audit",
        box=box.ROUNDED,
        header_style="bold blue",
        show_lines=True,
    )
    table.add_column("Round", justify="center", style="bold cyan")
    table.add_column("Task ID", justify="left")
    table.add_column("Assigned Trainers", justify="left")
    table.add_column("Sched Latency", justify="right")
    table.add_column("Status", justify="center")

    for r in coord_data.get("rounds", []):
        trainers = [a.get("trainer_node_id", "-") for a in r.get("assignments", [])]
        trainer_str = ", ".join(trainers) if trainers else "-"
        lat = f"{r.get('scheduling_latency_seconds', 0):.2f}s"
        stat = f"[green]{r.get('status', 'COMPLETED')}[/green]"
        table.add_row(str(r["round"]), r.get("task_id", "-"), trainer_str, lat, stat)

    console.print(table)
    console.print()


def generate_matplotlib_plot(eval_data: dict | None, timings_data: dict | None) -> None:
    """Generates high-resolution multi-panel plots using Matplotlib."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        console.print("[dim]Matplotlib not installed. Skipping PNG plot generation.[/dim]")
        return

    versions = (eval_data or {}).get("versions", [])
    rounds = (timings_data or {}).get("rounds", [])

    if not versions and not rounds:
        return

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("TrainSwarm: TinyStories Distributed Training Convergence & Efficiency", fontsize=16, fontweight="bold")

    # 1. Perplexity vs Version
    ax_ppl = axes[0, 0]
    if versions:
        v_labels = [f"v{v['version']}" for v in versions]
        ppls = [v["perplexity"] for v in versions]
        ax_ppl.plot(v_labels, ppls, marker="o", color="#1f77b4", linewidth=2.5, markersize=8)
        for i, (txt, p) in enumerate(zip(v_labels, ppls)):
            ax_ppl.annotate(f"{p:.2f}", (txt, p), textcoords="offset points", xytext=(0, 10), ha="center", fontweight="bold")
        ax_ppl.set_title("Perplexity Progression (Lower is Better)", fontweight="bold")
        ax_ppl.set_xlabel("Model Version")
        ax_ppl.set_ylabel("Perplexity")
        ax_ppl.grid(True, linestyle="--", alpha=0.6)

    # 2. Token Accuracy vs Version
    ax_acc = axes[0, 1]
    if versions:
        v_labels = [f"v{v['version']}" for v in versions]
        accs = [v["top1_accuracy"] * 100 for v in versions]
        ax_acc.plot(v_labels, accs, marker="s", color="#2ca02c", linewidth=2.5, markersize=8)
        for i, (txt, a) in enumerate(zip(v_labels, accs)):
            ax_acc.annotate(f"{a:.2f}%", (txt, a), textcoords="offset points", xytext=(0, 10), ha="center", fontweight="bold")
        ax_acc.set_title("Top-1 Token Prediction Accuracy", fontweight="bold")
        ax_acc.set_xlabel("Model Version")
        ax_acc.set_ylabel("Accuracy (%)")
        ax_acc.grid(True, linestyle="--", alpha=0.6)

    # 3. Cross-Entropy Loss vs Version
    ax_loss = axes[1, 0]
    if versions:
        v_labels = [f"v{v['version']}" for v in versions]
        losses = [v["loss"] for v in versions]
        ax_loss.plot(v_labels, losses, marker="^", color="#d62728", linewidth=2.5, markersize=8)
        for i, (txt, l) in enumerate(zip(v_labels, losses)):
            ax_loss.annotate(f"{l:.4f}", (txt, l), textcoords="offset points", xytext=(0, 10), ha="center")
        ax_loss.set_title("Cross-Entropy Loss Progression", fontweight="bold")
        ax_loss.set_xlabel("Model Version")
        ax_loss.set_ylabel("Loss")
        ax_loss.grid(True, linestyle="--", alpha=0.6)

    # 4. Process Elapsed Durations per Round
    ax_time = axes[1, 1]
    if rounds:
        r_labels = [f"Round {r['round']}" for r in rounds]
        durations = [r["elapsed_seconds"] for r in rounds]
        bars = ax_time.bar(r_labels, durations, color="#ff7f0e", width=0.55, edgecolor="black", alpha=0.85)
        for bar in bars:
            h = bar.get_height()
            ax_time.annotate(f"{h:.1f}s", xy=(bar.get_x() + bar.get_width() / 2, h), xytext=(0, 4), textcoords="offset points", ha="center")
        ax_time.set_title("Process Time Span per Training Round", fontweight="bold")
        ax_time.set_xlabel("Training Round")
        ax_time.set_ylabel("Elapsed Seconds")
        ax_time.grid(axis="y", linestyle="--", alpha=0.6)

    plt.tight_layout()
    PLOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(PLOT_PATH), dpi=200)
    plt.close()
    console.print(f"[bold green][+] Exported progression plot to: {PLOT_PATH}[/bold green]\n")


def main() -> None:
    render_header()
    eval_data = load_json_file(EVAL_PATH)
    timings_data = load_json_file(TIMINGS_PATH)
    coord_data = load_json_file(COORD_PATH)

    render_evaluations_table(eval_data)
    render_ascii_charts(eval_data)
    render_timings_table(timings_data)
    render_coordinator_table(coord_data)

    generate_matplotlib_plot(eval_data, timings_data)


if __name__ == "__main__":
    main()

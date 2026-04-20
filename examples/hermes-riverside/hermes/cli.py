from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from hermes.agent.loop import ToolTrace, run
from hermes.agent.prompts import system_message
from hermes.config import load_or_exit

app = typer.Typer(help="Otter Creek POC — agentic substation copilot over SP&L data.")
console = Console()


@app.command()
def chat() -> None:
    """Live chat REPL (requires a configured LLM provider)."""
    cfg = load_or_exit()
    console.print(
        Panel.fit(
            f"[bold]Otter — Riverside (SUB-001) copilot[/bold]\n"
            f"provider=[cyan]{cfg.provider}[/cyan]  model=[cyan]{cfg.model}[/cyan]\n\n"
            "Ask about feeders, hosting capacity, DER, outages, the Luke AFB microgrid, or switching.\n"
            "Ctrl-D to exit.",
            title="otter chat",
        )
    )
    history: list[dict] = [system_message()]
    while True:
        try:
            user_text = console.input("[bold green]you>[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            return
        if not user_text:
            continue

        def on_trace(trace: ToolTrace) -> None:
            console.print(f"[dim]tool: {trace.name}({trace.arguments}) → {len(str(trace.result))} chars[/dim]")

        turn = run(user_text, history=history, on_trace=on_trace)
        console.print(Panel(turn.final_text or "(no content)", title="otter"))


@app.command()
def summary() -> None:
    """Print Riverside overview pulled live from SP&L. Sanity check."""
    from hermes.data import spl

    load_or_exit()
    s = spl.riverside_summary()
    tbl = Table(title="Riverside (SUB-001) — Sisyphean Power & Light")
    tbl.add_column("field")
    tbl.add_column("value")
    for k in ("name", "voltage_high_kv", "voltage_low_kv", "rated_capacity_mva", "peak_load_mva", "num_transformers", "age_years", "status"):
        tbl.add_row(k, str(s.get(k)))
    console.print(tbl)

    feeders = spl.riverside_feeders()
    ftbl = Table(title="Feeders")
    for col in ("feeder_id", "name", "direction", "length_miles", "peak_load_mw", "num_customers"):
        ftbl.add_column(col)
    for f in feeders:
        ftbl.add_row(*(str(f.get(c)) for c in ("feeder_id", "name", "direction", "length_miles", "peak_load_mw", "num_customers")))
    console.print(ftbl)

    mg = spl.riverside_microgrid()
    if mg:
        console.print(
            f"\n[bold]Microgrid:[/bold] {mg['facility_name']} on {mg['feeder_id']} "
            f"({mg['solar_capacity_mw']} MW solar + {mg['battery_power_mw']} MW / "
            f"{mg['battery_energy_mwh']} MWh battery + {mg['chp_capacity_mw']} MW CHP), "
            f"can island {mg['island_duration_hours']} hrs"
        )

    hc = spl.riverside_hosting_capacity()
    console.print(
        f"\n[bold]Hosting capacity:[/bold] {hc['total_binding_kw']/1000:.1f} MW binding, "
        f"limiting factors: {hc['limiting_factors']}"
    )

    solar = spl.riverside_solar_summary()
    console.print(
        f"[bold]DER:[/bold] {solar['total_sites']} solar installs totaling "
        f"{solar['total_kw']/1000:.1f} MW"
    )

    outs = spl.riverside_outages()
    console.print(f"[bold]Outage history:[/bold] {len(outs)} events\n")


@app.command()
def ingest() -> None:
    """Rebuild the LanceDB vector store (reserved for future RAG over outage narratives)."""
    load_or_exit()
    console.print("[yellow]RAG ingest is not wired in the SP&L build yet.[/yellow]")


@app.command()
def eval(
    pairs: Path = typer.Option(Path("evals/qa_pairs.yaml"), help="YAML of QA pairs"),
    out: Path = typer.Option(Path("evals/results.md"), help="Markdown output"),
) -> None:
    """Run the eval harness (live inference required)."""
    from evals.run import run as run_eval

    load_or_exit()
    run_eval(pairs, out)


@app.command()
def record(
    scenario: str = typer.Option("all", help="Scenario id to record, or 'all'"),
    out_dir: Path = typer.Option(Path("fixtures/traces"), help="Where to write JSON traces"),
) -> None:
    """Record agent traces for the showcase notebook."""
    from scripts.record_traces import record_all, record_one

    load_or_exit()
    out_dir.mkdir(parents=True, exist_ok=True)
    if scenario == "all":
        record_all(out_dir)
    else:
        record_one(scenario, out_dir)


if __name__ == "__main__":
    app()

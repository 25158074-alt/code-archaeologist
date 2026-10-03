from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, TextColumn
from rich.table import Table
from rich.tree import Tree

from code_archaeologist.analysis.engine import ExcavationEngine
from code_archaeologist.analysis.deep_reasoning import DeepReasoningEngine
from code_archaeologist.analysis.fast_analysis import FastAnalysisEngine
from code_archaeologist.core.config import get_settings
from code_archaeologist.core.nebius_client import NebiusClient

app = typer.Typer(
    name="code-archaeologist",
    help="Code Archaeologist - Excavate codebases as archaeological sites",
    add_completion=False,
    no_args_is_help=True,
)
console = Console(force_terminal=True, color_system="truecolor", legacy_windows=False)


@app.command()
def excavate(
    path: Annotated[Path, typer.Argument(help="Path to codebase to excavate", exists=True, file_okay=False, dir_okay=True)],
    output: Annotated[Optional[Path], typer.Option("-o", "--output", help="Output report path")] = None,
    format: Annotated[str, typer.Option("-f", "--format", help="Output format: json, markdown, html")] = "json",
    deep: Annotated[bool, typer.Option("--deep/--no-deep", help="Enable deep reasoning with Nemotron 3 Ultra")] = True,
    fast: Annotated[bool, typer.Option("--fast/--no-fast", help="Enable fast analysis with Nemotron Nano/Super")] = True,
    save_raw: Annotated[bool, typer.Option("--save-raw", help="Save raw findings JSON")] = False,
):
    """Excavate a codebase - discover artifacts, strata, fossils, and ruins."""
    asyncio.run(_excavate_async(path, output, format, deep, fast, save_raw))


async def _excavate_async(
    path: Path,
    output: Optional[Path],
    format: str,
    deep: bool,
    fast: bool,
    save_raw: bool,
):
    settings = get_settings()

    if not settings.nebius.api_key:
        console.print("[red]ERROR: NEBIUS_API_KEY not set. Please configure in .env or environment.[/red]")
        raise typer.Exit(1)

    async with NebiusClient() as client:
        engine = ExcavationEngine(client)

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("[*] Excavating site...", total=None)
            report = await engine.excavate(path)
            progress.update(task, description="DONE: Excavation complete")

        if fast:
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("[*] Fast analysis...", total=None)
                fast_engine = FastAnalysisEngine(client)
                fast_results = await fast_engine.quick_scan(engine.parsed_files)
                report["fast_analysis"] = fast_results
                progress.update(task, description="DONE: Fast analysis complete")

        if deep:
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("[*] Deep reasoning with Nemotron 3 Ultra...", total=None)
                reasoning_engine = DeepReasoningEngine(client)

                from code_archaeologist.models.findings import Artifact, Fossil, Ruin, Stratum
                artifacts = [Artifact(**a) for a in report["artifacts"]]
                strata = [Stratum(**s) for s in report["strata"]]
                fossils = [Fossil(**f) for f in report["fossils"]]
                ruins = [Ruin(**r) for r in report["ruins"]]

                arch_analysis = await reasoning_engine.analyze_architecture(
                    artifacts, strata, fossils, ruins,
                    {"site_name": report["site_name"], "site_path": report["site_path"]}
                )
                report["deep_analysis"] = arch_analysis

                remediation = await reasoning_engine.generate_remediation_plan(ruins, strata, {
                    "site_name": report["site_name"],
                    "site_path": report["site_path"],
                })
                report["remediation_plan"] = remediation

                evolution = await reasoning_engine.predict_evolution(strata, artifacts, {
                    "site_name": report["site_name"],
                    "site_path": report["site_path"],
                })
                report["evolution_prediction"] = evolution

                progress.update(task, description="DONE: Deep reasoning complete")

        if save_raw:
            raw_path = output or Path(settings.output_dir) / f"{path.name}-raw.json"
            raw_path.write_text(json.dumps(report, indent=2))
            console.print(f"[green]SAVED: Raw report saved to {raw_path}[/green]")

        if format == "json":
            output_path = output or Path(settings.output_dir) / f"{path.name}-report.json"
            output_path.write_text(json.dumps(report, indent=2))
            console.print(f"[green]SAVED: JSON report saved to {output_path}[/green]")
        elif format == "markdown":
            output_path = output or Path(settings.output_dir) / f"{path.name}-report.md"
            output_path.write_text(_generate_markdown_report(report))
            console.print(f"[green]SAVED: Markdown report saved to {output_path}[/green]")
        elif format == "html":
            output_path = output or Path(settings.output_dir) / f"{path.name}-report.html"
            output_path.write_text(_generate_html_report(report))
            console.print(f"[green]SAVED: HTML report saved to {output_path}[/green]")

        _print_summary(report)


@app.command()
def scan(
    path: Annotated[Path, typer.Argument(help="Path to codebase", exists=True, file_okay=False, dir_okay=True)],
    file: Annotated[Optional[Path], typer.Option("--file", help="Analyze specific file")] = None,
):
    """Quick scan a codebase or file with Nemotron Nano/Super."""
    asyncio.run(_scan_async(path, file))


async def _scan_async(path: Path, file: Optional[Path]):
    settings = get_settings()

    if not settings.nebius.api_key:
        console.print("[red]ERROR: NEBIUS_API_KEY not set[/red]")
        raise typer.Exit(1)

    async with NebiusClient() as client:
        engine = ExcavationEngine(client)

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("[*] Parsing files...", total=None)
            await engine._discover_and_parse(path)
            await engine._build_dependency_graph()
            progress.update(task, description="DONE: Parsed")

        fast_engine = FastAnalysisEngine(client)

        if file:
            rel_path = file.relative_to(path).as_posix()
            if rel_path in engine.parsed_files:
                with Progress(
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task(f"[*] Analyzing {rel_path}...", total=None)
                    intent = await fast_engine.analyze_file_intent(engine.parsed_files[rel_path])
                    progress.update(task, description="DONE: Done")
                console.print(Panel.fit(json.dumps(intent, indent=2), title=f"File Intent: {rel_path}"))
            else:
                console.print(f"[red]File not found in parsed files: {rel_path}[/red]")
        else:
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("[*] Quick scan...", total=None)
                results = await fast_engine.quick_scan(engine.parsed_files)
                progress.update(task, description="DONE: Scan complete")

            _print_scan_results(results)


@app.command()
def explain(
    path: Annotated[Path, typer.Argument(help="Path to codebase", exists=True, file_okay=False, dir_okay=True)],
    finding_id: Annotated[str, typer.Argument(help="Finding ID to explain")],
    finding_type: Annotated[str, typer.Option("--type", help="Type: artifact, fossil, ruin")] = "ruin",
):
    """Explain a specific finding using Nemotron 3 Ultra."""
    asyncio.run(_explain_async(path, finding_id, finding_type))


async def _explain_async(path: Path, finding_id: str, finding_type: str):
    settings = get_settings()

    async with NebiusClient() as client:
        engine = ExcavationEngine(client)
        await engine.excavate(path)

        findings_map = {
            "artifact": engine.artifacts if hasattr(engine, 'artifacts') else [],
            "fossil": engine.fossils if hasattr(engine, 'fossils') else [],
            "ruin": engine.ruins if hasattr(engine, 'ruins') else [],
        }

        findings = findings_map.get(finding_type, [])
        finding = next((f for f in findings if f.id == finding_id), None)

        if not finding:
            console.print(f"[red]Finding {finding_id} not found[/red]")
            return

        reasoning_engine = DeepReasoningEngine(client)
        explanation = await reasoning_engine.explain_finding(finding, {
            "site_name": path.name,
            "total_files": len(engine.parsed_files),
        })

        console.print(Panel.fit(explanation, title=f"Explanation: {finding.name}"))


@app.command()
def remediation(
    path: Annotated[Path, typer.Argument(help="Path to codebase", exists=True, file_okay=False, dir_okay=True)],
    output: Annotated[Optional[Path], typer.Option("-o", "--output", help="Output plan path")] = None,
):
    """Generate remediation plan for technical debt."""
    asyncio.run(_remediation_async(path, output))


async def _remediation_async(path: Path, output: Optional[Path]):
    settings = get_settings()

    async with NebiusClient() as client:
        engine = ExcavationEngine(client)
        report = await engine.excavate(path)

        from code_archaeologist.models.findings import Ruin, Stratum
        ruins = [Ruin(**r) for r in report["ruins"]]
        strata = [Stratum(**s) for s in report["strata"]]

        reasoning_engine = DeepReasoningEngine(client)
        plan = await reasoning_engine.generate_remediation_plan(ruins, strata, {
            "site_name": report["site_name"],
            "site_path": report["site_path"],
        })

        if output:
            output.write_text(json.dumps(plan, indent=2))
            console.print(f"[green]SAVED: Remediation plan saved to {output}[/green]")
        else:
            console.print(Panel.fit(json.dumps(plan, indent=2), title="Remediation Plan"))


@app.command()
def predict(
    path: Annotated[Path, typer.Argument(help="Path to codebase", exists=True, file_okay=False, dir_okay=True)],
    output: Annotated[Optional[Path], typer.Option("-o", "--output", help="Output prediction path")] = None,
):
    """Predict codebase evolution over 6-12 months."""
    asyncio.run(_predict_async(path, output))


async def _predict_async(path: Path, output: Optional[Path]):
    settings = get_settings()

    async with NebiusClient() as client:
        engine = ExcavationEngine(client)
        report = await engine.excavate(path)

        from code_archaeologist.models.findings import Artifact, Stratum
        artifacts = [Artifact(**a) for a in report["artifacts"]]
        strata = [Stratum(**s) for s in report["strata"]]

        reasoning_engine = DeepReasoningEngine(client)
        prediction = await reasoning_engine.predict_evolution(strata, artifacts, {
            "site_name": report["site_name"],
            "site_path": report["site_path"],
        })

        if output:
            output.write_text(json.dumps(prediction, indent=2))
            console.print(f"[green]SAVED: Prediction saved to {output}[/green]")
        else:
            console.print(Panel.fit(json.dumps(prediction, indent=2), title="Evolution Prediction"))


def _print_summary(report: dict):
    summary = report.get("summary", {})

    console.print()
    console.print(Panel.fit(
        f"[bold]Site:[/bold] {report['site_name']}\n"
        f"[bold]Path:[/bold] {report['site_path']}\n"
        f"[bold]Excavated:[/bold] {report['excavated_at']}",
        title="Excavation Complete",
        border_style="green",
    ))

    stats_table = Table(title="Discovery Summary")
    stats_table.add_column("Category", style="cyan")
    stats_table.add_column("Count", style="magenta", justify="right")

    for category, count in [
        ("Artifacts", len(report.get("artifacts", []))),
        ("Strata", len(report.get("strata", []))),
        ("Fossils", len(report.get("fossils", []))),
        ("Ruins", len(report.get("ruins", []))),
    ]:
        stats_table.add_row(category, str(count))

    console.print(stats_table)

    if ruins := report.get("ruins", []):
        severity_table = Table(title="Ruins by Severity")
        severity_table.add_column("Severity", style="red")
        severity_table.add_column("Count", justify="right")

        from collections import Counter
        severity_counts = Counter(r["severity"] for r in ruins)
        for sev in ["critical", "high", "medium", "low", "info"]:
            if severity_counts.get(sev, 0) > 0:
                severity_table.add_row(sev.capitalize(), str(severity_counts[sev]))

        console.print(severity_table)

    if fast_analysis := report.get("fast_analysis", {}):
        health = fast_analysis.get("health_score", {})
        console.print(Panel.fit(
            f"[bold]Health Score:[/bold] {health.get('overall_score', 'N/A')}/100\n"
            f"[bold]Risk Level:[/bold] {health.get('risk_level', 'N/A').upper()}\n"
            f"[bold]Top Concerns:[/bold] {', '.join(health.get('top_concerns', []))}",
            title="Fast Health Assessment",
            border_style="yellow",
        ))


def _print_scan_results(results: dict):
    summary = results.get("summary", {})
    health = results.get("health_score", {})
    hotspots = results.get("hotspots", [])
    recs = results.get("quick_recommendations", [])

    console.print(Panel.fit(
        f"[bold]Files:[/bold] {summary.get('total_files', 0)}\n"
        f"[bold]LOC:[/bold] {summary.get('total_lines_of_code', 0):,}\n"
        f"[bold]Avg Complexity:[/bold] {summary.get('avg_complexity_per_file', 0):.1f}\n"
        f"[bold]Health:[/bold] {health.get('overall_score', 'N/A')}/100 ({health.get('risk_level', 'N/A')})",
        title="Quick Scan Results",
        border_style="blue",
    ))

    if hotspots:
        table = Table(title="Complexity Hotspots")
        table.add_column("File", style="cyan")
        table.add_column("Complexity", justify="right", style="red")
        table.add_column("LOC", justify="right")
        table.add_column("Functions", justify="right")
        table.add_column("Language", style="green")

        for h in hotspots[:10]:
            table.add_row(h["file"], str(h["complexity"]), str(h["lines"]), str(h["functions"]), h["language"])

        console.print(table)

    if recs:
        console.print("\n[bold]Quick Recommendations:[/bold]")
        for i, rec in enumerate(recs, 1):
            console.print(f"  {i}. {rec}")


def _generate_markdown_report(report: dict) -> str:
    lines = [
        f"# Excavation Report: {report['site_name']}",
        f"\n**Path:** `{report['site_path']}`  ",
        f"**Excavated:** {report['excavated_at']}  ",
        f"\n---\n",
        "## Summary\n",
        f"- **Artifacts:** {len(report.get('artifacts', []))}",
        f"- **Strata:** {len(report.get('strata', []))}",
        f"- **Fossils:** {len(report.get('fossils', []))}",
        f"- **Ruins:** {len(report.get('ruins', []))}",
        "\n## Artifacts\n",
    ]

    for a in report.get("artifacts", [])[:20]:
        lines.append(f"### {a['type'].title()}: {a['name']}")
        lines.append(f"- **Confidence:** {a['confidence']:.0%}")
        lines.append(f"- **Reasoning:** {a['reasoning']}")
        locs = ', '.join(f"`{l['file']}:{l['lines']}`" for l in a['locations'])
        lines.append(f"- **Locations:** {locs}")
        lines.append("")

    lines.append("## Strata\n")
    for s in report.get("strata", []):
        lines.append(f"### {s['type'].title()} Layer")
        lines.append(f"- **Files:** {s['file_count']}")
        lines.append(f"- **Stability:** {s['stability_score']:.0%}")
        lines.append(f"- **Coupling:** {s['coupling_score']:.1f}")
        lines.append(f"- **Cohesion:** {s['cohesion_score']:.0%}")
        lines.append("")

    lines.append("## Fossils\n")
    for f in report.get("fossils", [])[:20]:
        lines.append(f"### {f['type'].replace('_', ' ').title()}: {f['name']}")
        lines.append(f"- **Severity:** {f['severity']}")
        lines.append(f"- **Age:** {f['estimated_age_days']} days")
        lines.append(f"- **Reasoning:** {f['reasoning']}")
        lines.append(f"- **Remediation:** {f['remediation']}")
        lines.append("")

    lines.append("## Ruins\n")
    for r in report.get("ruins", [])[:20]:
        lines.append(f"### {r['type'].replace('_', ' ').title()}: {r['name']}")
        lines.append(f"- **Severity:** {r['severity']}")
        lines.append(f"- **Effort:** {r['effort_estimate']}")
        lines.append(f"- **Reasoning:** {r['reasoning']}")
        lines.append(f"- **Remediation:** {r['remediation']}")
        lines.append("")

    if deep := report.get("deep_analysis"):
        lines.append("## Deep Architectural Analysis\n")
        lines.append(f"**Style:** {deep.get('architectural_style', 'Unknown')}")
        lines.append(f"**Health Score:** {deep.get('health_score', 'N/A')}/100")
        lines.append(f"**Technical Debt Index:** {deep.get('technical_debt_index', 'N/A')}/100")
        lines.append("\n### Key Insights")
        for insight in deep.get("key_insights", []):
            lines.append(f"- {insight}")
        lines.append("\n### Strategic Recommendations")
        for rec in deep.get("strategic_recommendations", []):
            lines.append(f"- {rec}")

    return "\n".join(lines)


def _generate_html_report(report: dict) -> str:
    md = _generate_markdown_report(report)
    return f"""<!DOCTYPE html>
<html>
<head>
    <title>Code Archaeologist Report - {report['site_name']}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 900px; margin: 0 auto; padding: 2rem; line-height: 1.6; }}
        h1, h2, h3 {{ color: #2c3e50; }}
        code {{ background: #f4f4f4; padding: 0.2em 0.4em; border-radius: 3px; }}
        pre {{ background: #2d2d2d; color: #f8f8f2; padding: 1rem; border-radius: 5px; overflow-x: auto; }}
        table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
        th, td {{ padding: 0.5rem; border: 1px solid #ddd; text-align: left; }}
        th {{ background: #34495e; color: white; }}
        .panel {{ border: 1px solid #ddd; border-radius: 5px; padding: 1rem; margin: 1rem 0; background: #fafafa; }}
        .critical {{ border-left: 5px solid #e74c3c; }}
        .high {{ border-left: 5px solid #e67e22; }}
        .medium {{ border-left: 5px solid #f39c12; }}
        .low {{ border-left: 5px solid #3498db; }}
    </style>
</head>
<body>
{_markdown_to_html(md)}
</body>
</html>"""


def _markdown_to_html(md: str) -> str:
    html = md
    html = html.replace("\n## ", "\n<h2>").replace("## ", "<h2>").replace("\n### ", "\n<h3>").replace("### ", "<h3>")
    html = html.replace("\n# ", "\n<h1>").replace("# ", "<h1>")
    html = html.replace("**", "<strong>").replace("**", "</strong>")
    html = html.replace("`", "<code>").replace("`", "</code>")
    html = html.replace("\n- ", "\n<li>").replace("- ", "<li>")
    html = html.replace("\n\n", "</p><p>")
    html = f"<p>{html}</p>"
    html = html.replace("<p><h1>", "<h1>").replace("</h1></p>", "</h1>")
    html = html.replace("<p><h2>", "<h2>").replace("</h2></p>", "</h2>")
    html = html.replace("<p><h3>", "<h3>").replace("</h3></p>", "</h3>")
    html = html.replace("<p><li>", "<ul><li>").replace("</li></p>", "</li></ul>")
    return html


if __name__ == "__main__":
    app()
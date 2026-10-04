from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from code_archaeologist.analysis.engine import ExcavationEngine
from code_archaeologist.analysis.deep_reasoning import DeepReasoningEngine
from code_archaeologist.analysis.fast_analysis import FastAnalysisEngine
from code_archaeologist.core.config import get_settings
from code_archaeologist.core.nebius_client import NebiusClient


class ExcavationRequest(BaseModel):
    path: str = Field(..., description="Path to codebase")
    deep: bool = Field(default=True, description="Enable deep reasoning")
    fast: bool = Field(default=True, description="Enable fast analysis")


class ScanRequest(BaseModel):
    path: str = Field(..., description="Path to codebase")
    file: str | None = Field(default=None, description="Specific file to analyze")


class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: float
    message: str
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


jobs: dict[str, JobStatus] = {}

# Live endpoints only analyze code under this root (default: ./data), so the public
# API cannot be pointed at arbitrary server paths.
ALLOWED_ROOT = Path(os.environ.get("ARCHAEOLOGIST_ALLOWED_ROOT", "data")).resolve()


def resolve_safe_path(raw: str) -> Path:
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = ALLOWED_ROOT / candidate
    candidate = candidate.resolve()
    if candidate != ALLOWED_ROOT and ALLOWED_ROOT not in candidate.parents:
        raise HTTPException(403, f"Path must be inside {ALLOWED_ROOT}")
    if not candidate.is_dir():
        raise HTTPException(404, f"Directory not found: {raw}")
    return candidate


DEMO_REPORT = {
    "mode": "deterministic-demo",
    "site_name": "test_project",
    "summary": {
        "total_files": 2,
        "total_lines_of_code": 193,
        "total_functions": 32,
        "total_classes": 4,
        "languages": {"python": {"files": 2, "loc": 193}},
    },
    "health_score": {
        "overall_score": 67,
        "risk_level": "medium",
        "top_concerns": [
            "God class: UserService",
            "Unused public methods",
            "No automated tests",
        ],
    },
    "hotspots": [
        {"file": "service.py", "complexity": 12, "lines": 154, "functions": 27},
        {"file": "api.py", "complexity": 2, "lines": 39, "functions": 5},
    ],
    "findings": {
        "artifacts": 4,
        "strata": 0,
        "fossils": 15,
        "ruins": 1,
    },
    "note": "This public demo uses a bundled, deterministic fixture. Live scans route analysis prompts to the configured Nemotron models on Nebius.",
}


DEMO_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Code Archaeologist — Live Demo</title>
  <style>
    :root { color-scheme: dark; --ink:#f4efe4; --muted:#a9a18f; --gold:#e7b86b; --rust:#b9654b; --panel:#1d2224; --line:#374044; }
    * { box-sizing:border-box; } body { margin:0; font:16px/1.55 Inter,ui-sans-serif,system-ui,sans-serif; color:var(--ink); background:radial-gradient(circle at 80% 0%,#384238 0,#171b1c 48%,#101213 100%); }
    main { max-width:1080px; margin:0 auto; padding:56px 24px 72px; } .eyebrow { color:var(--gold); letter-spacing:.14em; text-transform:uppercase; font-size:.75rem; font-weight:700; }
    h1 { font:700 clamp(2.6rem,7vw,5.8rem)/.95 Georgia,serif; max-width:780px; margin:14px 0 20px; } h1 span { color:var(--gold); } .lede { color:var(--muted); max-width:680px; font-size:1.12rem; }
    .actions { display:flex; gap:12px; flex-wrap:wrap; margin:28px 0 34px; } button,a.button { border:1px solid var(--gold); border-radius:999px; padding:11px 18px; background:var(--gold); color:#171312; font-weight:800; cursor:pointer; text-decoration:none; } a.ghost { background:transparent; color:var(--ink); border-color:var(--line); }
    .status { color:var(--muted); min-height:25px; } .grid { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:22px 0; } .card { background:rgba(29,34,36,.82); border:1px solid var(--line); border-radius:14px; padding:18px; } .label { color:var(--muted); font-size:.8rem; text-transform:uppercase; letter-spacing:.08em; } .value { font:700 2.2rem Georgia,serif; color:var(--gold); margin-top:6px; }
    .columns { display:grid; grid-template-columns:1.1fr .9fr; gap:18px; } h2 { font:700 1.55rem Georgia,serif; margin:4px 0 14px; } ul { padding-left:20px; color:var(--muted); } li+li { margin-top:8px; } code { color:var(--gold); } footer { border-top:1px solid var(--line); margin-top:34px; padding-top:18px; color:var(--muted); font-size:.9rem; }
    @media (max-width:760px) { .grid,.columns { grid-template-columns:1fr 1fr; } .columns { display:block; } .columns .card+ .card { margin-top:16px; } } @media (max-width:440px) { .grid { grid-template-columns:1fr; } }
  </style>
</head>
<body><main>
  <div class="eyebrow">Public judging demo · deterministic fixture</div>
  <h1>Excavate your codebase as an <span>archaeological site.</span></h1>
  <p class="lede">Code Archaeologist maps patterns, architecture, dead code, and technical debt into a report that is useful to both humans and CI pipelines.</p>
  <div class="actions"><button id="run">Run sample excavation</button><a class="button ghost" href="/docs">Open API docs</a></div>
  <div class="status" id="status">Ready to excavate the bundled <code>test_project</code> fixture.</div>
  <section class="grid" id="metrics"></section>
  <section class="columns"><article class="card"><h2>Fast health assessment</h2><div id="health">Click “Run sample excavation” to load the report.</div></article><article class="card"><h2>Complexity hotspots</h2><div id="hotspots"></div></article></section>
  <footer>Live scans use the configured Nebius endpoint and Nemotron model tiers. The public sample is credential-free and does not accept arbitrary filesystem paths.</footer>
</main><script>
const $ = (id) => document.getElementById(id);
function render(data) {
  const cards = [['Files',data.summary.total_files],['Lines',data.summary.total_lines_of_code],['Functions',data.summary.total_functions],['Health',data.health_score.overall_score + '/100']];
  $('metrics').innerHTML = cards.map(([k,v]) => `<div class="card"><div class="label">${k}</div><div class="value">${v}</div></div>`).join('');
  $('health').innerHTML = `<p><strong>${data.health_score.risk_level.toUpperCase()} risk</strong> — ${data.health_score.top_concerns.join(', ')}.</p><ul>${Object.entries(data.findings).map(([k,v]) => `<li>${k}: ${v}</li>`).join('')}</ul>`;
  $('hotspots').innerHTML = `<ul>${data.hotspots.map(h => `<li><code>${h.file}</code> · complexity ${h.complexity} · ${h.lines} lines</li>`).join('')}</ul>`;
}
async function run() { $('run').disabled = true; $('status').textContent = 'Excavating sample files…'; try { const r = await fetch('/demo'); render(await r.json()); $('status').textContent = 'Excavation complete — report loaded from the running API.'; } catch(e) { $('status').textContent = 'Demo request failed: ' + e; } finally { $('run').disabled = false; } }
$('run').addEventListener('click', run); run();
</script></body></html>"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not get_settings().nebius.api_key:
        print("WARNING: NEBIUS_API_KEY not set")
    yield


app = FastAPI(
    title="Code Archaeologist API",
    description="Excavate codebases as archaeological sites using NVIDIA Nemotron models on Nebius",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def run_excavation(job_id: str, site_path: Path, request: ExcavationRequest):
    def update(status: str | None = None, progress: float | None = None, message: str | None = None) -> None:
        job = jobs[job_id]
        if status is not None:
            job.status = status
        if progress is not None:
            job.progress = progress
        if message is not None:
            job.message = message
        job.updated_at = datetime.now()

    update("running", 0.1, "Excavating...")

    try:
        async with NebiusClient() as client:
            engine = ExcavationEngine(client)
            report = await engine.excavate(site_path)

            if request.fast:
                update(progress=0.5, message="Fast analysis...")
                report["fast_analysis"] = await FastAnalysisEngine(client).quick_scan(engine.parsed_files)

            if request.deep:
                update(progress=0.7, message="Deep reasoning with Nemotron 3 Ultra...")
                reasoning_engine = DeepReasoningEngine(client)
                context = {"site_name": report["site_name"], "site_path": report["site_path"]}
                report["deep_analysis"] = await reasoning_engine.analyze_architecture(
                    engine.artifacts, engine.strata, engine.fossils, engine.ruins, context
                )
                report["remediation_plan"] = await reasoning_engine.generate_remediation_plan(
                    engine.ruins, engine.strata, context
                )
                report["evolution_prediction"] = await reasoning_engine.predict_evolution(
                    engine.strata, engine.artifacts, context
                )

            jobs[job_id].result = report
            update("completed", 1.0, "Excavation complete")

    except Exception as e:
        jobs[job_id].error = str(e)
        update("failed", message=f"Failed: {e}")


@app.post("/excavate", response_model=JobStatus)
async def start_excavation(request: ExcavationRequest, background_tasks: BackgroundTasks):
    site_path = resolve_safe_path(request.path)
    job_id = str(uuid.uuid4())[:8]
    job = JobStatus(
        job_id=job_id,
        status="pending",
        progress=0.0,
        message="Queued",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    jobs[job_id] = job
    background_tasks.add_task(run_excavation, job_id, site_path, request)
    return job


@app.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    return jobs[job_id]


@app.get("/jobs")
async def list_jobs():
    return list(jobs.values())


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing_page():
    return HTMLResponse(DEMO_HTML)


@app.get("/demo")
async def demo_report():
    return DEMO_REPORT


@app.post("/scan")
async def quick_scan(request: ScanRequest):
    site_path = resolve_safe_path(request.path)
    async with NebiusClient() as client:
        engine = ExcavationEngine(client)
        await engine._discover_and_parse(site_path)
        await engine._build_dependency_graph()

        fast_engine = FastAnalysisEngine(client)

        if request.file:
            file_path = Path(request.file)
            if not file_path.is_absolute():
                file_path = site_path / file_path
            try:
                rel_path = file_path.resolve().relative_to(site_path).as_posix()
            except ValueError:
                raise HTTPException(400, "File must be inside the scanned path")
            if rel_path not in engine.parsed_files:
                raise HTTPException(404, f"File not found: {rel_path}")
            intent = await fast_engine.analyze_file_intent(engine.parsed_files[rel_path])
            return {"file": rel_path, "analysis": intent}

        return await fast_engine.quick_scan(engine.parsed_files)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "code-archaeologist"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

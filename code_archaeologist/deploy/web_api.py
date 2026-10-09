from __future__ import annotations

import os
import uuid
import io
import shutil
import asyncio
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from code_archaeologist.analysis.deep_reasoning import DeepReasoningEngine
from code_archaeologist.analysis.engine import ExcavationEngine
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
SITE_DIR = Path(__file__).resolve().parents[2] / "site"
if not SITE_DIR.is_dir():
    SITE_DIR = Path("site").resolve()
ALLOWED_ROOT = Path(os.environ.get("ARCHAEOLOGIST_ALLOWED_ROOT", "data")).resolve()
try:
    ALLOWED_ROOT.mkdir(parents=True, exist_ok=True)
except OSError:
    pass


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
    "summary": {"total_files": 2, "total_lines_of_code": 193, "total_functions": 32, "total_classes": 4, "languages": {"python": {"files": 2, "loc": 193}}},
    "health_score": {"overall_score": 67, "risk_level": "medium", "top_concerns": ["God class: UserService", "Unused public methods", "No automated tests", "Service layer has 78% of business logic"]},
    "artifacts": [
        {"id": "art-001", "type": "pattern", "name": "Repository pattern", "description": "UserRepository keeps persistence behind a narrow interface, making the service testable.", "location": {"file": "service.py", "lines": "8-24"}, "confidence": 0.94, "tier": "super"},
        {"id": "art-002", "type": "convention", "name": "Controller boundary", "description": "APIController translates domain objects into stable response dictionaries.", "location": {"file": "api.py", "lines": "8-26"}, "confidence": 0.89, "tier": "nano"},
        {"id": "art-003", "type": "idiom", "name": "Dataclass domain model", "description": "User is a compact, serializable domain record with explicit fields.", "location": {"file": "service.py", "lines": "10-16"}, "confidence": 0.96, "tier": "nano"},
        {"id": "art-004", "type": "pattern", "name": "Defensive lookup", "description": "The service returns None for missing users instead of leaking a storage exception.", "location": {"file": "service.py", "lines": "25-32"}, "confidence": 0.86, "tier": "super"},
    ],
    "strata": [
        {"id": "str-001", "type": "foundation", "name": "Foundation", "description": "Data model and repository primitives.", "files": ["service.py"], "depth": 1, "stability_score": 0.88, "coupling_score": 0.21, "cohesion_score": 0.91},
        {"id": "str-002", "type": "core", "name": "Core domain", "description": "UserService owns most business behavior and needs decomposition.", "files": ["service.py"], "depth": 2, "stability_score": 0.58, "coupling_score": 0.72, "cohesion_score": 0.44},
        {"id": "str-003", "type": "feature", "name": "Feature surface", "description": "User operations exposed to clients.", "files": ["api.py"], "depth": 3, "stability_score": 0.64, "coupling_score": 0.61, "cohesion_score": 0.70},
        {"id": "str-004", "type": "integration", "name": "Integration boundary", "description": "Controller-to-service handoff and response mapping.", "files": ["api.py", "service.py"], "depth": 4, "stability_score": 0.49, "coupling_score": 0.78, "cohesion_score": 0.53},
        {"id": "str-005", "type": "test", "name": "Test stratum", "description": "Currently disconnected: no automated tests were found.", "files": [], "depth": 5, "stability_score": 0.18, "coupling_score": 0.02, "cohesion_score": 0.20},
    ],
    "fossils": [
        {"id": "fos-001", "type": "dead_code", "name": "legacy_function", "description": "Public function has no call sites in the repository.", "severity": "high", "estimated_age_days": 412, "location": {"file": "service.py", "lines": "104-118"}, "reasoning": "The symbol is exported but never referenced by APIController or tests.", "remediation": "Delete after one release of deprecation telemetry.", "tier": "nano"},
        {"id": "fos-002", "type": "unused_import", "name": "Unused os import", "description": "Import is retained from an earlier filesystem implementation.", "severity": "low", "estimated_age_days": 260, "location": {"file": "service.py", "lines": "3-3"}, "reasoning": "Tree-sitter found no name usage in the module.", "remediation": "Remove the import.", "tier": "nano"},
        {"id": "fos-003", "type": "commented_out", "name": "Commented migration block", "description": "Old cache migration code is preserved as a 22-line comment.", "severity": "medium", "estimated_age_days": 188, "location": {"file": "service.py", "lines": "120-141"}, "reasoning": "The block has not executed since the repository history split.", "remediation": "Move context to an ADR, then delete the commented code.", "tier": "super"},
    ],
    "ruins": [
        {"id": "rui-001", "type": "god_class", "name": "God Class: UserService", "description": "One class owns persistence, caching, validation, orchestration, and notification concerns.", "severity": "critical", "effort_estimate": "large", "locations": [{"file": "service.py", "lines": "18-101"}], "reasoning": "UserService contains 27 methods and 154 lines. It reaches across repository, cache, validation, and notification responsibilities.", "remediation": "Extract UserRepository, UserValidator, and NotificationPort. Keep UserService as an application coordinator.", "metrics": {"methods": 27, "lines": 154, "complexity": 12}, "tier": "ultra"},
        {"id": "rui-002", "type": "leaky_abstraction", "name": "Leaky controller boundary", "description": "APIController exposes service return shapes directly to clients.", "severity": "high", "effort_estimate": "medium", "locations": [{"file": "api.py", "lines": "8-26"}], "reasoning": "The controller knows storage-oriented fields and has no response schema.", "remediation": "Add response DTOs and a mapper at the integration boundary.", "metrics": {"callers": 4, "fields": 9}, "tier": "super"},
        {"id": "rui-003", "type": "missing_tests", "name": "Missing test stratum", "description": "The feature surface has no automated tests protecting refactors.", "severity": "high", "effort_estimate": "medium", "locations": [{"file": "api.py", "lines": "1-39"}], "reasoning": "No test files or test imports were detected for the two production modules.", "remediation": "Start with contract tests for list_users and get_user, then add service unit tests.", "metrics": {"coverage": 0, "public_methods": 5}, "tier": "nano"},
    ],
    "routing_log": [
        {"model": "Nano", "call": "health + hotspot triage", "tokens": 1284, "latency": "842ms", "cost": 0.03},
        {"model": "Super", "call": "file intent + strata mapping", "tokens": 4620, "latency": "1.8s", "cost": 0.11},
        {"model": "Ultra", "call": "ruin explanations", "tokens": 4320, "latency": "4.6s", "cost": 0.18},
        {"model": "Ultra", "call": "forecast + remediation", "tokens": 8910, "latency": "6.2s", "cost": 0.26},
    ],
    "remediation_plan": [
        {"priority": 1, "title": "Split UserService responsibilities", "effort": "large", "estimate": "3–5 days", "why": "Unblocks safe feature work and reduces change ripple."},
        {"priority": 2, "title": "Add API contract tests", "effort": "medium", "estimate": "1–2 days", "why": "Creates a safety net before the decomposition."},
        {"priority": 3, "title": "Quarantine and delete fossils", "effort": "small", "estimate": "2–4 hours", "why": "Removes stale paths and lowers cognitive load."},
    ],
    "forecast": [
        {"when": "Now", "title": "Stabilize the surface", "text": "Add contract tests and pin response DTOs before refactoring."},
        {"when": "3 months", "title": "Extract application seams", "text": "Split repository, validation, and notification ports from UserService."},
        {"when": "6 months", "title": "Rebalance the strata", "text": "Feature work moves through an application service; coupling falls."},
        {"when": "12 months", "title": "A healthier site", "text": "Test stratum becomes connected and the service becomes composable."},
    ],
    "note": "This public demo uses a bundled, deterministic fixture with non-empty artifacts, strata, fossils, and ruins. Live scans route analysis prompts to the configured Nemotron models on Nebius Token Factory.",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not get_settings().nebius.api_key:
        print("WARNING: NEBIUS_API_KEY not set")
    yield


app = FastAPI(title="Code Archaeologist API", description="Excavate codebases as archaeological sites using NVIDIA Nemotron models on Nebius Token Factory", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


def _fallback_plan(ruins: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"priority": i, "title": r.get("name", "Address technical debt"), "effort": r.get("effort_estimate", "medium"), "estimate": r.get("effort_estimate", "medium"), "why": r.get("reasoning", r.get("description", "Reduce maintenance risk."))} for i, r in enumerate(ruins[:5], 1)]


def to_dashboard(report: dict[str, Any]) -> dict[str, Any]:
    """Normalize an excavation report to the exact shape consumed by render()."""
    summary = dict(report.get("summary") or {})
    summary.setdefault("total_files", summary.get("total_files_analyzed", 0))
    summary.setdefault("total_lines_of_code", 0)
    summary.setdefault("total_functions", 0)
    summary.setdefault("total_classes", 0)
    fast = report.get("fast_analysis") or {}
    health = fast.get("health_score") or report.get("health_score") or {"overall_score": 0, "risk_level": "unknown", "top_concerns": []}
    if isinstance(health, (int, float)):
        health = {"overall_score": health, "risk_level": "unknown", "top_concerns": []}
    plan = report.get("remediation_plan")
    if isinstance(plan, dict):
        plan = plan.get("phases") or plan.get("quick_wins") or []
    if isinstance(plan, list):
        plan = [{
            "priority": item.get("priority", item.get("phase", i)),
            "title": item.get("title", item.get("name", f"Remediation phase {i}")),
            "effort": item.get("effort", item.get("estimated_effort", "medium")),
            "estimate": item.get("estimate", item.get("estimated_effort", "medium")),
            "why": item.get("why", item.get("risk_mitigation", item.get("description", "Reduce architectural risk."))),
        } for i, item in enumerate(plan, 1)]
    forecast = report.get("evolution_prediction") or report.get("forecast") or {}
    if isinstance(forecast, dict):
        forecast = forecast.get("forecast") or forecast.get("timeline") or forecast.get("stratum_evolution") or []
    if isinstance(forecast, dict):
        forecast = [{"when": k, "title": k, "text": str(v)} for k, v in forecast.items()]
    result = dict(report)
    result["summary"] = summary
    result["health_score"] = health
    result["remediation_plan"] = plan or _fallback_plan(result.get("ruins", []))
    result["forecast"] = forecast or []
    result["artifacts"] = [{**x, "tier": x.get("tier", "super")} for x in result.get("artifacts", [])]
    result["fossils"] = [{**x, "tier": x.get("tier", "nano")} for x in result.get("fossils", [])]
    result["ruins"] = [{**x, "tier": x.get("tier", "super")} for x in result.get("ruins", [])]
    result["strata"] = [{**x, "coupling_score": max(0.0, min(1.0, float(x.get("coupling_score", 0))))} for x in result.get("strata", [])]
    result.setdefault("routing_log", [])
    return result


async def run_excavation(job_id: str, site_path: Path, request: ExcavationRequest):
    def update(status=None, progress=None, message=None):
        job = jobs[job_id]
        if status is not None: job.status = status
        if progress is not None: job.progress = progress
        if message is not None: job.message = message
        job.updated_at = datetime.now()

    update("running", 0.1, "Parsing with tree-sitter...")
    report = None
    warnings = []
    try:
        async with NebiusClient() as client:
            engine = ExcavationEngine(client)
            report = await engine.excavate(site_path)
            if request.fast:
                if not get_settings().nebius.api_key:
                    warnings.append("NEBIUS_API_KEY is not configured; fast LLM analysis was skipped.")
                else:
                    try:
                        update(progress=0.5, message="Nano scan...")
                        report["fast_analysis"] = await FastAnalysisEngine(client).quick_scan(engine.parsed_files)
                    except Exception as exc:
                        warnings.append(f"Fast analysis unavailable: {exc}")
            if request.deep:
                if not get_settings().nebius.api_key:
                    warnings.append("NEBIUS_API_KEY is not configured; LLM stages were skipped.")
                    update(message="Local analysis complete; LLM stages skipped (no NEBIUS_API_KEY)")
                else:
                    update(progress=0.7, message="Ultra reasoning...")
                    reasoning_engine = DeepReasoningEngine(client)
                    context = {"site_name": report["site_name"], "site_path": report["site_path"]}
                    try:
                        report["deep_analysis"] = await reasoning_engine.analyze_architecture(engine.artifacts, engine.strata, engine.fossils, engine.ruins, context)
                    except Exception as exc:
                        warnings.append(f"Deep architecture analysis unavailable: {exc}")
                    try:
                        report["remediation_plan"] = await reasoning_engine.generate_remediation_plan(engine.ruins, engine.strata, context)
                    except Exception as exc:
                        warnings.append(f"Remediation plan unavailable: {exc}")
                    try:
                        report["evolution_prediction"] = await reasoning_engine.predict_evolution(engine.strata, engine.artifacts, context)
                    except Exception as exc:
                        warnings.append(f"Evolution prediction unavailable: {exc}")
            report["routing_log"] = client.routing_log
            report["warnings"] = warnings
            dashboard = to_dashboard(report)
            dashboard["job_id"] = job_id
            jobs[job_id].result = dashboard
            update("completed", 1.0, "Excavation complete" if not warnings else "Excavation complete with warnings")
    except Exception as exc:
        jobs[job_id].error = str(exc)
        update("failed", message=f"Failed: {exc}")


def queue_excavation(site_path: Path, background_tasks: BackgroundTasks, request: ExcavationRequest | None = None) -> JobStatus:
    job_id = str(uuid.uuid4())
    now = datetime.now()
    request = request or ExcavationRequest(path=str(site_path))
    jobs[job_id] = JobStatus(job_id=job_id, status="pending", progress=0.0, message="Queued", created_at=now, updated_at=now)
    background_tasks.add_task(run_excavation, job_id, site_path, request)
    return jobs[job_id]


@app.post("/excavate", response_model=JobStatus)
async def start_excavation(request: ExcavationRequest, background_tasks: BackgroundTasks):
    return queue_excavation(resolve_safe_path(request.path), background_tasks, request)


@app.post("/upload", response_model=JobStatus)
async def upload_repository(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Upload a .zip archive")
    blob = await file.read(50 * 1024 * 1024 + 1)
    if len(blob) > 50 * 1024 * 1024:
        raise HTTPException(413, "ZIP uploads are limited to 50 MB")
    upload_dir = ALLOWED_ROOT / ("upload-" + uuid.uuid4().hex)
    upload_dir.mkdir(parents=True, exist_ok=False)
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            members = [m for m in archive.infolist() if not any(part == "__MACOSX" or part.startswith("._") for part in Path(m.filename).parts)]
            if len(members) > 5000 or sum(m.file_size for m in members) > 200 * 1024 * 1024:
                raise HTTPException(413, "Archive exceeds extraction limits")
            for member in members:
                target = (upload_dir / member.filename).resolve()
                if target != upload_dir.resolve() and upload_dir.resolve() not in target.parents:
                    raise HTTPException(400, "Archive contains an unsafe path")
                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise HTTPException(400, "Archive symlinks are not accepted")
            archive.extractall(upload_dir)
    except zipfile.BadZipFile:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise HTTPException(400, "Invalid ZIP archive")
    except Exception:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise
    # Common GitHub ZIP layout: one top-level folder; otherwise scan extracted root.
    children = list(upload_dir.iterdir())
    site_path = children[0] if len(children) == 1 and children[0].is_dir() else upload_dir
    return queue_excavation(site_path, background_tasks, ExcavationRequest(path=str(site_path)))


@app.post("/repository", response_model=JobStatus)
async def clone_repository(request: dict[str, str], background_tasks: BackgroundTasks):
    url = request.get("url", "").strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {"github.com", "www.github.com"} or parsed.username or parsed.password:
        raise HTTPException(400, "Only public HTTPS GitHub repository URLs are supported")
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) not in (2, 4) or (len(parts) == 4 and parts[2] != "tree"):
        raise HTTPException(400, "Enter a repository URL such as https://github.com/owner/repo or /tree/branch")
    dest = ALLOWED_ROOT / ("repo-" + uuid.uuid4().hex)
    try:
        proc = await asyncio.create_subprocess_exec("git", "clone", "--depth", "200", "--", url, str(dest), stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        if proc.returncode:
            shutil.rmtree(dest, ignore_errors=True)
            raise HTTPException(400, "Could not clone this public repository: " + stderr.decode(errors="replace")[-300:])
    except asyncio.TimeoutError:
        shutil.rmtree(dest, ignore_errors=True)
        raise HTTPException(408, "Repository clone timed out")
    return queue_excavation(dest, background_tasks)


@app.get("/jobs/{job_id}/source")
async def source_snippet(job_id: str, file: str, lines: str = "1-20"):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    path = Path(jobs[job_id].result.get("site_path", "")) if jobs[job_id].result else None
    if not path or not path.is_dir():
        raise HTTPException(404, "Source is no longer available")
    target = (path / file).resolve()
    if path not in target.parents or not target.is_file():
        raise HTTPException(400, "File must be inside the scanned path")
    try:
        start, end = (int(x) for x in lines.split("-", 1))
    except ValueError:
        raise HTTPException(400, "lines must be START-END")
    content = target.read_text(encoding="utf-8", errors="replace").splitlines()
    start, end = max(1, start), min(len(content), end)
    return {"file": file, "start": start, "end": end, "code": [[n, content[n-1]] for n in range(start, end + 1)]}


@app.post("/explain")
async def explain_finding(payload: dict[str, Any]):
    async with NebiusClient() as client:
        finding = payload.get("finding") or {}
        engine = DeepReasoningEngine(client)
        class Finding:
            def to_dict(self): return finding
        return {"explanation": await engine.explain_finding(Finding(), payload.get("context") or {})}


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
    site_file = SITE_DIR / "index.html"
    if site_file.exists():
        return HTMLResponse(site_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Code Archaeologist</h1><p>Frontend bundle unavailable.</p>")


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
            return {"file": rel_path, "analysis": await fast_engine.analyze_file_intent(engine.parsed_files[rel_path])}
        return await fast_engine.quick_scan(engine.parsed_files)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "code-archaeologist", "demo_findings": {"artifacts": len(DEMO_REPORT["artifacts"]), "strata": len(DEMO_REPORT["strata"]), "fossils": len(DEMO_REPORT["fossils"]), "ruins": len(DEMO_REPORT["ruins"])} }


if __name__ == "__main__":
    import uvicorn

    # Hosting platforms (Render, Railway, Cloud Run, Heroku, ...) inject $PORT.
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))

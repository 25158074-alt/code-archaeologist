from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
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

    update("running", 0.1, "Parsing with tree-sitter...")
    try:
        async with NebiusClient() as client:
            engine = ExcavationEngine(client)
            report = await engine.excavate(site_path)
            if request.fast:
                update(progress=0.5, message="Nano scan...")
                report["fast_analysis"] = await FastAnalysisEngine(client).quick_scan(engine.parsed_files)
            if request.deep:
                update(progress=0.7, message="Ultra reasoning...")
                reasoning_engine = DeepReasoningEngine(client)
                context = {"site_name": report["site_name"], "site_path": report["site_path"]}
                report["deep_analysis"] = await reasoning_engine.analyze_architecture(engine.artifacts, engine.strata, engine.fossils, engine.ruins, context)
                report["remediation_plan"] = await reasoning_engine.generate_remediation_plan(engine.ruins, engine.strata, context)
                report["evolution_prediction"] = await reasoning_engine.predict_evolution(engine.strata, engine.artifacts, context)
            jobs[job_id].result = report
            update("completed", 1.0, "Excavation complete")
    except Exception as e:
        jobs[job_id].error = str(e)
        update("failed", message=f"Failed: {e}")


@app.post("/excavate", response_model=JobStatus)
async def start_excavation(request: ExcavationRequest, background_tasks: BackgroundTasks):
    site_path = resolve_safe_path(request.path)
    job_id = str(uuid.uuid4())[:8]
    now = datetime.now()
    jobs[job_id] = JobStatus(job_id=job_id, status="pending", progress=0.0, message="Queued", created_at=now, updated_at=now)
    background_tasks.add_task(run_excavation, job_id, site_path, request)
    return jobs[job_id]


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
    site_file = Path("site/index.html")
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
    uvicorn.run(app, host="0.0.0.0", port=8000)

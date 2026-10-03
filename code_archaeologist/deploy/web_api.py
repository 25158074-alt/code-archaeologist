from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if not settings.nebius.api_key:
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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def run_excavation(job_id: str, request: ExcavationRequest):
    jobs[job_id].status = "running"
    jobs[job_id].message = "Initializing..."

    try:
        settings = get_settings()
        async with NebiusClient() as client:
            engine = ExcavationEngine(client)

            jobs[job_id].progress = 0.1
            jobs[job_id].message = "Parsing files..."
            await engine._discover_and_parse(Path(request.path))
            await engine._build_dependency_graph()
            await engine._analyze_git_history()

            jobs[job_id].progress = 0.4
            jobs[job_id].message = "Excavating..."
            report = await engine.excavate(request.path)

            if request.fast:
                jobs[job_id].progress = 0.6
                jobs[job_id].message = "Fast analysis..."
                fast_engine = FastAnalysisEngine(client)
                fast_results = await fast_engine.quick_scan(engine.parsed_files)
                report["fast_analysis"] = fast_results

            if request.deep:
                jobs[job_id].progress = 0.7
                jobs[job_id].message = "Deep reasoning with Nemotron 3 Ultra..."
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

            jobs[job_id].progress = 1.0
            jobs[job_id].status = "completed"
            jobs[job_id].message = "Excavation complete"
            jobs[job_id].result = report
            jobs[job_id].updated_at = datetime.now()

    except Exception as e:
        jobs[job_id].status = "failed"
        jobs[job_id].error = str(e)
        jobs[job_id].message = f"Failed: {e}"
        jobs[job_id].updated_at = datetime.now()


@app.post("/excavate", response_model=JobStatus)
async def start_excavation(request: ExcavationRequest, background_tasks: BackgroundTasks):
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
    background_tasks.add_task(run_excavation, job_id, request)
    return job


@app.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    return jobs[job_id]


@app.get("/jobs")
async def list_jobs():
    return list(jobs.values())


@app.post("/scan")
async def quick_scan(request: ScanRequest):
    settings = get_settings()
    async with NebiusClient() as client:
        engine = ExcavationEngine(client)
        await engine._discover_and_parse(Path(request.path))
        await engine._build_dependency_graph()

        fast_engine = FastAnalysisEngine(client)

        if request.file:
            rel_path = Path(request.file).relative_to(Path(request.path)).as_posix()
            if rel_path in engine.parsed_files:
                intent = await fast_engine.analyze_file_intent(engine.parsed_files[rel_path])
                return {"file": rel_path, "analysis": intent}
            else:
                raise HTTPException(404, f"File not found: {rel_path}")
        else:
            results = await fast_engine.quick_scan(engine.parsed_files)
            return results


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "code-archaeologist"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from code_archaeologist.deploy import web_api


def test_dashboard_contract_contains_render_keys(monkeypatch, tmp_path):
    monkeypatch.setattr(web_api, "ALLOWED_ROOT", tmp_path)
    site = tmp_path / "site"
    site.mkdir()
    (site / "main.py").write_text("def hello():\n    return 1\n")
    client = TestClient(web_api.app)
    job = client.post("/excavate", json={"path": "site", "deep": False, "fast": False}).json()
    state = client.get(f"/jobs/{job['job_id']}").json()
    assert state["status"] == "completed"
    result = state["result"]
    for key in ("summary", "health_score", "artifacts", "strata", "fossils", "ruins", "remediation_plan", "forecast", "routing_log", "warnings"):
        assert key in result
    assert {"total_files", "total_lines_of_code", "total_functions", "total_classes"} <= result["summary"].keys()
    assert all("tier" in item for group in ("artifacts", "fossils", "ruins") for item in result[group])


def test_repository_route_accepts_www_and_uses_async_git(monkeypatch, tmp_path):
    monkeypatch.setattr(web_api, "ALLOWED_ROOT", tmp_path)
    class Proc:
        returncode = 0
        async def communicate(self):
            return b"", b""
    calls = []
    async def fake_clone(*args, **kwargs):
        calls.append((args, kwargs))
        dest = Path(args[-1])
        dest.mkdir()
        return Proc()
    monkeypatch.setattr(web_api.asyncio, "create_subprocess_exec", fake_clone)
    client = TestClient(web_api.app)
    response = client.post("/repository", json={"url": "https://www.github.com/owner/repo"})
    assert response.status_code == 200
    assert calls and "--depth" in calls[0][0] and "200" in calls[0][0]

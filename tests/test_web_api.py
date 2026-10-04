from fastapi.testclient import TestClient

from code_archaeologist.deploy import web_api

client = TestClient(web_api.app)


def test_demo_and_health():
    assert client.get("/health").json()["status"] == "healthy"
    demo = client.get("/demo").json()
    assert demo["summary"]["total_files"] == 2
    assert all(demo[key] for key in ("artifacts", "strata", "fossils", "ruins"))


def test_rejects_paths_outside_allowed_root():
    r = client.post("/scan", json={"path": "/etc"})
    assert r.status_code == 403
    r = client.post("/excavate", json={"path": "../../.."})
    assert r.status_code == 403

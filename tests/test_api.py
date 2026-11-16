import os
import tempfile

os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["ANTHROPIC_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_full_flow():
    with TestClient(app) as c:
        assert c.get("/api/health").json()["status"] == "ok"
        r = c.post("/api/extract", json={"text": "Total: $50\nEmail: a@b.com", "fields": ["total"], "mode": "auto"})
        assert r.status_code == 200
        body = r.json()
        assert body["custom_fields"]["total"] == "$50"
        assert body["meta"]["mode_used"] == "rules"

        assert len(c.get("/api/history").json()) == 1
        assert c.get(f"/api/history/{body['id']}").status_code == 200

        for fmt in ("json", "csv", "md"):
            e = c.post("/api/export", json={"result": body, "format": fmt})
            assert e.status_code == 200 and e.text

        assert c.delete(f"/api/history/{body['id']}").status_code == 200
        assert c.get(f"/api/history/{body['id']}").status_code == 404


def test_file_upload_and_errors():
    with TestClient(app) as c:
        r = c.post("/api/extract/file", files={"file": ("a.txt", b"Name: Riya\nPhone: +91 98765 43210")}, data={"fields": "name"})
        assert r.status_code == 200 and r.json()["custom_fields"]["name"] == "Riya"
        bad = c.post("/api/extract/file", files={"file": ("a.exe", b"xx")})
        assert bad.status_code == 415
        assert c.post("/api/extract", json={"text": ""}).status_code == 422

"""Photoreal render API: input checks (no Blender needed)."""
import json


def test_status_reports_availability(client):
    r = client.get("/api/v1/render/status")
    assert r.status_code == 200
    body = r.json()
    assert "available" in body and "trees_total" in body


def test_rejects_non_gltf(client):
    r = client.post("/api/v1/render", files={"scene": ("scene.glb", b"not a gltf", "model/gltf-binary"),
                                            "meta": ("meta.json", b"{}", "application/json")})
    assert r.status_code == 400


def test_rejects_missing_camera(client):
    glb = b"glTF" + b"\x00" * 16
    r = client.post("/api/v1/render", files={"scene": ("scene.glb", glb, "model/gltf-binary"),
                                            "meta": ("meta.json", json.dumps({"camera": {"matrix": [1, 2]}}).encode(), "application/json")})
    assert r.status_code == 400


def test_unknown_job_is_404(client):
    assert client.get("/api/v1/render/nope").status_code == 404
    assert client.get("/api/v1/render/nope/image").status_code == 404

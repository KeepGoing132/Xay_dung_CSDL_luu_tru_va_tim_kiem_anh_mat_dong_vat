"""Check moved web assets and API against a disposable copy of real data."""
from dataclasses import replace
from contextlib import closing
from pathlib import Path
import csv
import base64
import hashlib
from io import BytesIO
import os
import shutil
import sqlite3
import sys
import tempfile
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from starlette.testclient import TestClient
from uvicorn import Config
from backend import app as web
from backend.src.config import AppConfig
from backend.src.repository import Repository
from backend.src.search_service import SearchService
from backend.src.calibration import calibration_path


def main():
    original = AppConfig.default()
    assert original.project_root == ROOT
    assert original.db_path.is_file()
    assert original.migration_path.is_file()
    server = Config("backend.app:app")
    server.load()
    with original.default_manifest_path.open(
        encoding="utf-8-sig", newline=""
    ) as stream:
        query = next(row for row in csv.DictReader(stream) if row["split"] == "test")
    payload = original.resolve_data_path(query["relative_path"]).read_bytes()
    with tempfile.TemporaryDirectory(prefix="cbir-layout-") as directory:
        scratch = Path(directory)
        config = replace(
            original, data_root=scratch / "data", db_path=scratch / "app.db",
            artifacts_root=scratch / "artifacts",
        )
        with closing(sqlite3.connect(original.db_path.as_uri() + "?mode=ro", uri=True)) as source:
            with closing(sqlite3.connect(config.db_path)) as target:
                source.backup(target)
            paths = source.execute(
                "SELECT original_path, processed_path FROM images "
                "WHERE split='gallery' AND active=1 AND quality_status='approved'"
            ).fetchall()
        for row_paths in paths:
            for relative in row_paths:
                target = config.resolve_data_path(relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original.resolve_data_path(relative), target)
        config.ensure_runtime_dirs()
        if calibration_path(original).exists():
            calibration_path(config).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(calibration_path(original), calibration_path(config))
        repository = Repository(config)
        repository.create_schema()
        bundle = repository.ensure_baseline_bundle()
        service = SearchService(config, repository)
        web.services = lambda: (config, repository, service)
        previous_cwd = Path.cwd()
        try:
            os.chdir(scratch)
            with TestClient(web.app) as client:
                for url in ("/", "/static/app.css", "/static/motion.css", "/static/motion.js", "/static/app.js", "/api/dashboard"):
                    response = client.get(url)
                    assert response.status_code == 200, (url, response.status_code)
                    print(f"GET {url}: 200")
                homepage = client.get("/")
                assert homepage.headers["cache-control"] == "no-cache"
                assert 'id="motion-toggle"' in homepage.text
                for asset in ("app.css", "motion.css", "motion.js", "app.js"):
                    digest = hashlib.sha256((ROOT / "frontend" / "static" / asset).read_bytes()).hexdigest()[:12]
                    assert f"/static/{asset}?v={digest}" in homepage.text
                dashboard = client.get("/api/dashboard").json()
                assert dashboard["stats"]["approved_gallery"] == 500
                assert len(dashboard["stats"]["by_species"]) == 6
                assert "6 nhóm động vật" in client.get("/").text
                response = client.post(
                    "/api/search", files={"image": ("query.jpg", payload, "image/jpeg")},
                )
                assert response.status_code == 200, response.text
                result = response.json()
                ids = [item["image_id"] for item in result["items"]]
                assert result["candidate_count"] == 500
                assert len(ids) == len(set(ids)) == 5
                for item in result["items"]:
                    with Image.open(BytesIO(base64.b64decode(item["image"].split(",", 1)[1]))) as preview:
                        assert preview.mode == "RGB" and preview.size == (512, 512)
                assert [item["rank"] for item in result["items"]] == [1, 2, 3, 4, 5]
                assert result["query"]["dimensions"] == {name: spec.dimension for name, spec in bundle.configs.items()}
                assert len(result["items"][0]["scores"]) == len(bundle.configs) + 1
                with Image.open(BytesIO(base64.b64decode(result["query"]["rgb"].split(",", 1)[1]))) as preview:
                    assert preview.size == (original.image_size, original.image_size)
                history = client.get(f"/api/history/{result['query_id']}")
                assert history.status_code == 200
                assert [item["image_id"] for item in history.json()["items"]] == ids
                assert [item["image"] for item in history.json()["items"]] == [item["image"] for item in result["items"]]
                assert client.post("/api/search").status_code == 422
                assert client.get("/api/history/2147483647").status_code == 404
                print(f"Search/history: 500 candidates, 5 unique results {ids}")
                print("Error responses: missing image=422, missing history=404")
                print("Assets and API passed from outside project working directory")
        finally:
            os.chdir(previous_cwd)
    print("Real database was opened read-only; queries ran on a temporary copy")


if __name__ == "__main__":
    main()

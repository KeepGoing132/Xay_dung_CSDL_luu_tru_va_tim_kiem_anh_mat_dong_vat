from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import uuid4

import numpy as np
from PIL import Image
import pytest

from backend.src.config import AppConfig, BUNDLE_NAME


def pytest_configure(config):
    if config.option.basetemp is None:
        root = Path(__file__).resolve().parents[1] / "tmp" / "pytest-runs"
        root.mkdir(parents=True, exist_ok=True)
        config.option.basetemp = str(root / uuid4().hex)


def image_bytes(array: np.ndarray, mode: str | None = None) -> bytes:
    stream = BytesIO()
    Image.fromarray(array, mode=mode).save(stream, format="PNG")
    return stream.getvalue()


@pytest.fixture
def app_config(tmp_path: Path) -> AppConfig:
    project = tmp_path / "project"
    data = project / "data"
    migration_source = Path(__file__).resolve().parents[1] / "migrations" / "001_init.sql"
    migration = project / "migrations" / "001_init.sql"
    migration.parent.mkdir(parents=True)
    migration.write_text(migration_source.read_text(encoding="utf-8"), encoding="utf-8")
    for source in migration_source.parent.glob("[0-9][0-9][0-9]_*.sql"):
        (migration.parent / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    config = AppConfig(
        project_root=project,
        data_root=data,
        db_path=data / "foreground4.db",
        migration_path=migration,
        artifacts_root=project / "artifacts",
        bundle_name=BUNDLE_NAME,
    )
    config.ensure_runtime_dirs()
    return config

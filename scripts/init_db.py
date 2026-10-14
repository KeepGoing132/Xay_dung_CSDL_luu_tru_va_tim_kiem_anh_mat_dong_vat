from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.src.config import AppConfig
from backend.src.repository import Repository


def main() -> None:
    config = AppConfig.default()
    config.ensure_runtime_dirs()
    repository = Repository(config)
    repository.create_schema()
    bundle = repository.ensure_baseline_bundle()
    print(f"Database: {config.db_path}")
    print(f"Bundle: {bundle.name} {bundle.config_ids}")


if __name__ == "__main__":
    main()


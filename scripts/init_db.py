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
    print(f"Database: {config.db_path}")
    print("Schema ready; run scripts/prepare_dataset.py before retrieval")


if __name__ == "__main__":
    main()


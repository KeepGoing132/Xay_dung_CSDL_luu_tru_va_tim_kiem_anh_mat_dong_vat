"""Run the same 512px processing pipeline used by the web application."""
import argparse
import json
from pathlib import Path
import sys
import threading
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.src.config import AppConfig, NATIVE512_BUNDLE_NAME
from backend.src.processing_service import DatasetProcessingService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["remove_background", "extract_features", "pipeline"])
    parser.add_argument("--limit", type=int, help="Small trial; feature import accepts only available cutouts")
    args = parser.parse_args()
    service = DatasetProcessingService(AppConfig.default(profile=NATIVE512_BUNDLE_NAME))
    def progress(**values):
        print(json.dumps(values, ensure_ascii=False), flush=True)
    result = service.run(args.action, args.limit, progress, threading.Event(), uuid4().hex)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

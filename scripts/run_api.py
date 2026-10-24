"""Run the Occlusion FastAPI service.

Usage:
    uv run python scripts/run_api.py

Requires the ingested collection at ``./data/qdrant_storage`` and Bedrock
credentials in ``.env``.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from src.service.app import create_app  # noqa: E402


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    uvicorn.run(
        create_app(),
        host=os.getenv("OCCLUSION_API_HOST", "0.0.0.0"),
        port=int(os.getenv("OCCLUSION_API_PORT", "8000")),
    )


if __name__ == "__main__":
    main()

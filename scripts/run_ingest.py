"""CLI entry point for the ingestion pipeline.

Thin wrapper so the documented command works from the repo root
(AGENTS.md: ``uv run python scripts/run_ingest.py``); all real logic
lives in ``src/ingest/ingestion_pipeline.py``.

Usage:
    uv run python scripts/run_ingest.py              # full corpus (PDFs + 11 HTML sources)
    uv run python scripts/run_ingest.py --pdf-only   # local PDFs only (offline-safe)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# `python scripts/x.py` puts scripts/ (not the repo root) on sys.path, so
# `src.*` imports need the repo root added explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingest.ingestion_pipeline import IngestionPipeline  # noqa: E402

logger = logging.getLogger("run_ingest")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest the Occlusion corpus into Qdrant (parse -> chunk -> index)."
    )
    parser.add_argument(
        "--pdf-only",
        action="store_true",
        help="Skip the 11 HTML sources; ingest local PDFs from data/raw only.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # None -> the pipeline's default corpus; [] -> PDFs only.
    html_urls = [] if args.pdf_only else None
    pipeline = IngestionPipeline(html_urls=html_urls)
    summary = pipeline.run()
    logger.info("Pipeline summary: %s", summary)


if __name__ == "__main__":
    main()

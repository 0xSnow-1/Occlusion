"""Tests for src/ingest/ingestion_pipeline.py (end-to-end ingest)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from langchain_core.documents import Document

from src.ingest.ingestion_pipeline import IngestionPipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _documents(n: int = 2) -> list[Document]:
    return [
        Document(
            page_content="Brushing twice a day prevents cavities. " * 10,
            metadata={"doc_id": f"doc-{i}", "source": "test"},
        )
        for i in range(n)
    ]


@pytest.fixture
def pipeline() -> IngestionPipeline:
    """Pipeline against in-memory Qdrant and a small chunk size."""
    return IngestionPipeline(
        collection_name="test-pipeline",
        qdrant_path=":memory:",
        chunk_size=100,
        chunk_overlap=0,
    )


# ---------------------------------------------------------------------------
# Pipeline tests
# ---------------------------------------------------------------------------

class TestRun:
    """Verify the end-to-end parse -> chunk -> index flow."""

    def test_run_returns_summary_counts(self, pipeline):
        with patch(
            "src.ingest.ingestion_pipeline.load_all_documents",
            return_value=_documents(),
        ):
            summary = pipeline.run()

        assert summary["pages"] == 2
        assert summary["chunks"] > 0
        assert summary["points"] == summary["chunks"]

    def test_run_creates_and_fills_collection(self, pipeline):
        with patch(
            "src.ingest.ingestion_pipeline.load_all_documents",
            return_value=_documents(),
        ):
            summary = pipeline.run()

        assert pipeline._store.collection_exists()
        stored = pipeline._store.client.count(pipeline.collection_name).count
        assert stored == summary["points"]

    def test_run_with_empty_corpus_returns_zeroes(self, pipeline):
        with patch(
            "src.ingest.ingestion_pipeline.load_all_documents",
            return_value=[],
        ):
            summary = pipeline.run()

        assert summary == {"pages": 0, "chunks": 0, "points": 0}

    def test_recreate_collection_clears_stale_points(self, pipeline):
        """A second, smaller run must leave no leftover points behind."""
        with patch(
            "src.ingest.ingestion_pipeline.load_all_documents",
            return_value=_documents(2),
        ):
            first = pipeline.run()

        with patch(
            "src.ingest.ingestion_pipeline.load_all_documents",
            return_value=_documents(1),
        ):
            second = pipeline.run()

        assert second["points"] < first["points"]
        stored = pipeline._store.client.count(pipeline.collection_name).count
        assert stored == second["points"]

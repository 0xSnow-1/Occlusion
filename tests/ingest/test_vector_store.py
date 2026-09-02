"""Tests for src/ingest/vector_store.py (Qdrant vector store)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from qdrant_client.models import (
    Distance,
    SparseVectorParams,
    VectorParams,
)

from src.ingest.vector_store import (
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
    VectorStore,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store(**kwargs: Any) -> VectorStore:
    """Create a VectorStore with sensible defaults for tests."""
    defaults = {
        "collection_name": "test-collection",
        "qdrant_url": ":memory:",
    }
    defaults.update(kwargs)
    return VectorStore(**defaults)


def _sample_docs() -> list[dict]:
    return [
        {"text": "Brushing twice a day prevents cavities.", "doc_id": "oral-hygiene", "source_url": "https://example.com"},
        {"text": "Flossing removes plaque between teeth.", "doc_id": "flossing", "source_url": "https://example.com"},
    ]


# ---------------------------------------------------------------------------
# Collection creation tests
# ---------------------------------------------------------------------------

class TestCreateCollection:
    """Verify collection lifecycle with an in-memory Qdrant instance."""

    def test_creates_collection_with_dense_and_sparse(self):
        store = _make_store()
        store.create_collection()

        info = store.client.get_collection(store.collection_name)
        assert DENSE_VECTOR_NAME in info.config.params.vectors
        assert SPARSE_VECTOR_NAME in info.config.params.sparse_vectors

    def test_dense_vector_is_cosine_384dim(self):
        store = _make_store()
        store.create_collection()

        info = store.client.get_collection(store.collection_name)
        dense_params = info.config.params.vectors[DENSE_VECTOR_NAME]
        assert dense_params.distance == Distance.COSINE
        assert dense_params.size == 384

    def test_sparse_vector_params_present(self):
        store = _make_store()
        store.create_collection()

        info = store.client.get_collection(store.collection_name)
        sparse = info.config.params.sparse_vectors[SPARSE_VECTOR_NAME]
        assert isinstance(sparse, SparseVectorParams)

    def test_collection_exists_after_creation(self):
        store = _make_store()
        assert not store.collection_exists()

        store.create_collection()
        assert store.collection_exists()

    def test_create_collection_is_idempotent(self):
        store = _make_store()
        store.create_collection()
        store.create_collection()  # second call should not error

        info = store.client.get_collection(store.collection_name)
        assert DENSE_VECTOR_NAME in info.config.params.vectors


# ---------------------------------------------------------------------------
# Payload index tests
# ---------------------------------------------------------------------------

class TestPayloadIndexes:
    """Verify payload index creation calls (local Qdrant ignores them, so verify the calls)."""

    def test_create_payload_index_called_for_doc_id(self):
        store = _make_store()
        mock_client = MagicMock()
        mock_client.collection_exists.return_value = False
        mock_client.get_embedding_size.return_value = 384
        store._client = mock_client

        store.create_collection()

        fields = [c.kwargs["field_name"] for c in mock_client.create_payload_index.call_args_list]
        assert "doc_id" in fields

    def test_create_payload_index_called_for_source_url(self):
        store = _make_store()
        mock_client = MagicMock()
        mock_client.collection_exists.return_value = False
        mock_client.get_embedding_size.return_value = 384
        store._client = mock_client

        store.create_collection()

        fields = [c.kwargs["field_name"] for c in mock_client.create_payload_index.call_args_list]
        assert "source_url" in fields

    def test_create_payload_index_called_for_title(self):
        store = _make_store()
        mock_client = MagicMock()
        mock_client.collection_exists.return_value = False
        mock_client.get_embedding_size.return_value = 384
        store._client = mock_client

        store.create_collection()

        fields = [c.kwargs["field_name"] for c in mock_client.create_payload_index.call_args_list]
        assert "title" in fields

    def test_three_payload_indexes_created(self):
        store = _make_store()
        mock_client = MagicMock()
        mock_client.collection_exists.return_value = False
        mock_client.get_embedding_size.return_value = 384
        store._client = mock_client

        store.create_collection()

        assert mock_client.create_payload_index.call_count == 3


# ---------------------------------------------------------------------------
# Upsert tests (use mocks to avoid downloading fastembed models)
# ---------------------------------------------------------------------------

class TestUpsertDocuments:
    """Verify upsert logic without needing fastembed model downloads."""

    @patch.object(VectorStore, "client", new_callable=lambda: property(lambda self: MagicMock()))
    def test_upsert_empty_list_returns_zero(self, mock_client_prop):
        store = _make_store()
        count = store.upsert_documents([])
        assert count == 0

    def test_upsert_calls_client_upsert(self):
        store = _make_store()
        mock_client = MagicMock()
        mock_client.collection_exists.return_value = True
        mock_client.get_embedding_size.return_value = 384
        store._client = mock_client

        docs = [{"text": "Hello world", "doc_id": "test"}]
        count = store.upsert_documents(docs)

        assert count == 1
        mock_client.upsert.assert_called_once()

    def test_upsert_point_has_both_vectors(self):
        store = _make_store()
        mock_client = MagicMock()
        mock_client.collection_exists.return_value = True
        store._client = mock_client

        docs = [{"text": "Test sentence", "doc_id": "x"}]
        store.upsert_documents(docs)

        call_kwargs = mock_client.upsert.call_args
        point = call_kwargs.kwargs["points"][0]
        assert DENSE_VECTOR_NAME in point.vector
        assert SPARSE_VECTOR_NAME in point.vector

    def test_upsert_payload_excludes_text(self):
        store = _make_store()
        mock_client = MagicMock()
        mock_client.collection_exists.return_value = True
        store._client = mock_client

        docs = [{"text": "Content here", "doc_id": "abc", "source_url": "https://x.com"}]
        store.upsert_documents(docs)

        point = mock_client.upsert.call_args.kwargs["points"][0]
        assert "text" not in point.payload
        assert point.payload["doc_id"] == "abc"
        assert point.payload["source_url"] == "https://x.com"

    def test_upsert_deterministic_ids(self):
        store = _make_store()
        mock_client = MagicMock()
        mock_client.collection_exists.return_value = True
        store._client = mock_client

        docs = [{"text": "A"}, {"text": "B"}, {"text": "C"}]
        store.upsert_documents(docs)

        points = mock_client.upsert.call_args.kwargs["points"]
        ids = [p.id for p in points]
        assert ids == [0, 1, 2]


# ---------------------------------------------------------------------------
# Delete collection tests
# ---------------------------------------------------------------------------

class TestDeleteCollection:
    """Verify collection deletion."""

    def test_delete_existing_collection(self):
        store = _make_store()
        store.create_collection()
        assert store.collection_exists()

        store.delete_collection()
        assert not store.collection_exists()

    def test_delete_nonexistent_collection_is_noop(self):
        store = _make_store()
        store.delete_collection()  # should not error


# ---------------------------------------------------------------------------
# Lazy client tests
# ---------------------------------------------------------------------------

class TestLazyClient:
    """Verify client is created lazily on first access."""

    def test_client_not_created_at_init(self):
        store = _make_store()
        assert store._client is None

    def test_client_created_on_access(self):
        store = _make_store()
        _ = store.client
        assert store._client is not None

    def test_same_client_returned(self):
        store = _make_store()
        c1 = store.client
        c2 = store.client
        assert c1 is c2

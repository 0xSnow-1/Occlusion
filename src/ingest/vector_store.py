"""Qdrant vector store for the Occlusion ingestion pipeline.

Manages collection lifecycle (create, delete) and document upsert
for hybrid dense + sparse retrieval.

Stack:
    - qdrant-client with fastembed integration for local embedding
    - Dense: all-MiniLM-L6-v2 (384-dim, cosine)
    - Sparse: Splade_PP_en_v1 (BM25-style, IDF-weighted)
"""

from __future__ import annotations

import logging
from typing import Sequence

from qdrant_client import QdrantClient, models
from qdrant_client.models import (
    Distance,
    PointStruct,
    SparseIndexParams,
    SparseVectorParams,
    VectorParams,
)

logger = logging.getLogger(__name__)

_DEFAULT_DENSE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_DEFAULT_SPARSE_MODEL = "prithivida/Splade_PP_en_v1"

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"


class VectorStore:
    """Qdrant collection with hybrid dense + sparse vector support.

    Parameters
    ----------
    collection_name:
        Name of the Qdrant collection.
    qdrant_url:
        Qdrant server URL.  Pass ``":memory:"`` for an in-memory instance
        (useful for tests).
    qdrant_api_key:
        API key for Qdrant Cloud.  Ignored for ``:memory:`` and local URLs.
    dense_model:
        fastembed model name for dense embeddings.
    sparse_model:
        fastembed model name for sparse embeddings.
    """

    def __init__(
        self,
        collection_name: str,
        qdrant_url: str = "./data/qdrant_storage",
        qdrant_api_key: str | None = None,
        dense_model: str = _DEFAULT_DENSE_MODEL,
        sparse_model: str = _DEFAULT_SPARSE_MODEL,
    ) -> None:
        self.collection_name = collection_name
        self._qdrant_url = qdrant_url
        self._qdrant_api_key = qdrant_api_key
        self._dense_model = dense_model
        self._sparse_model = sparse_model
        self._client: QdrantClient | None = None

    @property
    def client(self) -> QdrantClient:
        """Lazily connect to Qdrant.

        Three connection modes, chosen by the shape of ``qdrant_url``:

        * ``":memory:"``        -- in-memory instance (useful for tests)
        * ``http(s)://...`` URL -- Qdrant server / Qdrant Cloud
        * anything else         -- local filesystem path for persistent
                                   on-disk storage (e.g. ``./data/qdrant_storage``)
        """
        if self._client is None:
            if self._qdrant_url == ":memory:":
                self._client = QdrantClient(":memory:")
            elif self._qdrant_url.startswith(("http://", "https://")):
                self._client = QdrantClient(
                    url=self._qdrant_url,
                    api_key=self._qdrant_api_key,
                )
            else:
                self._client = QdrantClient(path=self._qdrant_url)
            logger.info("Connected to Qdrant at %s", self._qdrant_url)
        return self._client

    def create_collection(self) -> None:
        """Create the collection with dense + sparse vector configs and payload indexes."""
        if self.collection_exists():
            logger.info("Collection '%s' already exists, skipping creation", self.collection_name)
            return

        dense_size = self.client.get_embedding_size(self._dense_model)

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                DENSE_VECTOR_NAME: VectorParams(
                    size=dense_size,
                    distance=Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                SPARSE_VECTOR_NAME: SparseVectorParams(
                    index=SparseIndexParams(on_disk=False),
                ),
            },
        )
        logger.info(
            "Created collection '%s' (dense dim=%d, cosine)",
            self.collection_name,
            dense_size,
        )

        for field, schema_type in [
            ("doc_id", models.PayloadSchemaType.KEYWORD),
            ("source_url", models.PayloadSchemaType.KEYWORD),
            ("title", models.TextIndexParams(
                type="text",
                tokenizer=models.TokenizerType.WORD,
                min_token_len=2,
                max_token_len=20,
                lowercase=True,
            )),
        ]:
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name=field,
                field_schema=schema_type,
            )
        logger.info("Payload indexes created for doc_id, source_url, title")

    def collection_exists(self) -> bool:
        """Check whether the collection already exists."""
        return self.client.collection_exists(self.collection_name)

    def upsert_documents(self, documents: Sequence[dict]) -> int:
        """Upsert documents with both dense and sparse embeddings.

        Each document dict must contain a ``"text"`` key and any metadata
        keys to store as payload (e.g. ``doc_id``, ``source_url``).

        fastembed handles embedding at upsert time via ``models.Document``.

        Returns the number of points upserted.
        """
        if not documents:
            return 0

        points = []
        for idx, doc in enumerate(documents):
            text = doc["text"]
            payload = {k: v for k, v in doc.items() if k != "text"}

            points.append(
                PointStruct(
                    id=idx,
                    vector={
                        DENSE_VECTOR_NAME: models.Document(text=text, model=self._dense_model),
                        SPARSE_VECTOR_NAME: models.Document(text=text, model=self._sparse_model),
                    },
                    payload=payload,
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        logger.info("Upserted %d points to '%s'", len(points), self.collection_name)
        return len(points)

    def delete_collection(self) -> None:
        """Delete the collection if it exists."""
        if self.collection_exists():
            self.client.delete_collection(self.collection_name)
            logger.info("Deleted collection '%s'", self.collection_name)

"""Document chunking for the Occlusion data ingestion stage.

Takes raw LangChain Documents produced by `document_parser` and produces
chunked documents ready for vector-store ingestion.

Stack:
    - RecursiveCharacterTextSplitter (LangChain) for chunking

Embedding happens at upsert time, not here: `vector_store.py` wraps each
chunk in a fastembed ``models.Document`` so the dense (all-MiniLM-L6-v2)
and sparse (Splade_PP_en_v1) vectors are computed inside
``client.upsert()`` (see DECISIONS/hybrid-qdrant-vector-store.md).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


class DocumentChunker:
    """Split documents into smaller chunks for vector-store ingestion.

    Parameters
    ----------
    chunk_size:
        Maximum character count per chunk.  Passed directly to
        ``RecursiveCharacterTextSplitter``.
    chunk_overlap:
        Character overlap between consecutive chunks.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )

    # -- public API -----------------------------------------------------------

    def chunk_documents(self, documents: Sequence[Document]) -> list[Document]:
        """Split each document into smaller chunks.

        Chunk metadata is inherited from the source document.  Two extra
        fields are added:

        * ``chunk_index`` - 0-based position within the source document.
        * ``chunk_total`` - total number of chunks produced from that doc.
        """
        all_chunks: list[Document] = []
        for doc in documents:
            splits = self._splitter.split_text(doc.page_content)
            total = len(splits)
            for idx, text in enumerate(splits):
                meta = {**doc.metadata, "chunk_index": idx, "chunk_total": total}
                all_chunks.append(Document(page_content=text, metadata=meta))
        logger.info(
            "Chunked %d documents into %d chunks", len(documents), len(all_chunks)
        )
        return all_chunks

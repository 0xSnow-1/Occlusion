"""Chunking and embedding pipeline for the Occlusion data ingestion stage.

Takes raw LangChain Documents produced by `document_parser` and produces
chunked, embedded documents ready for vector-store ingestion.

Stack:
    - RecursiveCharacterTextSplitter (LangChain) for chunking
    - SentenceTransformer (sentence-transformers) for dense embeddings
"""

from __future__ import annotations

import logging
from typing import List, Sequence

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_DEFAULT_EMBED_MODEL = "all-MiniLM-L6-v2"


class DocumentChunker:
    """Chunk documents and compute dense embeddings for each chunk.

    Parameters
    ----------
    chunk_size:
        Maximum character count per chunk.  Passed directly to
        ``RecursiveCharacterTextSplitter``.
    chunk_overlap:
        Character overlap between consecutive chunks.
    embedding_model:
        Name of the ``sentence-transformers`` model to load.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        embedding_model: str = _DEFAULT_EMBED_MODEL,
    ) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )
        self._embed_model_name = embedding_model
        self._model: SentenceTransformer | None = None

    # -- lazy-loaded property --------------------------------------------------

    @property
    def model(self) -> SentenceTransformer:
        """Lazily load the SentenceTransformer so import-time is fast."""
        if self._model is None:
            logger.info("Loading embedding model: %s", self._embed_model_name)
            self._model = SentenceTransformer(self._embed_model_name)
            logger.debug("Model loaded successfully")
        return self._model

    # -- public API -----------------------------------------------------------

    def chunk_documents(self, documents: Sequence[Document]) -> List[Document]:
        """Split each document into smaller chunks.

        Chunk metadata is inherited from the source document.  Two extra
        fields are added:

        * ``chunk_index`` - 0-based position within the source document.
        * ``chunk_total`` - total number of chunks produced from that doc.
        """
        all_chunks: List[Document] = []
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

    def embed_documents(self, documents: Sequence[Document]) -> List[Document]:
        """Compute a dense embedding vector for each document.

        The embedding is stored in ``doc.metadata["embedding"]`` as a
        plain list of floats (JSON-serializable for Qdrant / pgvector).
        """
        if not documents:
            return []
        texts = [doc.page_content for doc in documents]
        logger.info("Embedding %d chunks ...", len(texts))
        vectors = self.model.encode(texts, show_progress_bar=False)
        embedded: List[Document] = []
        for doc, vec in zip(documents, vectors):
            meta = {**doc.metadata, "embedding": vec.tolist()}
            embedded.append(Document(page_content=doc.page_content, metadata=meta))
        logger.info("Embedding complete for %d chunks", len(embedded))
        return embedded

    def process(self, documents: Sequence[Document]) -> List[Document]:
        """End-to-end: chunk then embed.  Convenience wrapper."""
        chunks = self.chunk_documents(documents)
        return self.embed_documents(chunks)




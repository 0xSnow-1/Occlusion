<<<<<<< HEAD
"""Chunking and embedding pipeline for the Occlusion data ingestion stage.

Takes raw LangChain Documents produced by `document_parser` and produces
chunked, embedded documents ready for vector-store ingestion.

Stack:
    - RecursiveCharacterTextSplitter (LangChain) for chunking
    - SentenceTransformer (sentence-transformers) for dense embeddings
=======
"""Document chunking for the Occlusion data ingestion stage.

Takes raw LangChain Documents produced by `document_parser` and produces
chunked documents ready for vector-store ingestion.

Stack:
    - RecursiveCharacterTextSplitter (LangChain) for chunking

Embedding happens at upsert time, not here: `vector_store.py` wraps each
chunk in a fastembed ``models.Document`` so the dense (all-MiniLM-L6-v2)
and sparse (Splade_PP_en_v1) vectors are computed inside
``client.upsert()`` (see DECISIONS/hybrid-qdrant-vector-store.md).
>>>>>>> feature/retrieve
"""

from __future__ import annotations

<<<<<<< HEAD
import argparse
=======
>>>>>>> feature/retrieve
import logging
from typing import List, Sequence

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
<<<<<<< HEAD
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Default model kept as a module-level constant so both the class and CLI
# reference the same value without duplication.
_DEFAULT_EMBED_MODEL = "all-MiniLM-L6-v2"


class DocumentChunker:
    """Chunk documents and compute dense embeddings for each chunk.
=======

logger = logging.getLogger(__name__)


class DocumentChunker:
    """Split documents into smaller chunks for vector-store ingestion.
>>>>>>> feature/retrieve

    Parameters
    ----------
    chunk_size:
        Maximum character count per chunk.  Passed directly to
        ``RecursiveCharacterTextSplitter``.
    chunk_overlap:
        Character overlap between consecutive chunks.
<<<<<<< HEAD
    embedding_model:
        Name of the ``sentence-transformers`` model to load.
=======
>>>>>>> feature/retrieve
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
<<<<<<< HEAD
        embedding_model: str = _DEFAULT_EMBED_MODEL,
=======
>>>>>>> feature/retrieve
    ) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )
<<<<<<< HEAD
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
=======
>>>>>>> feature/retrieve

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
<<<<<<< HEAD

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


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Chunk and embed documents from the Occlusion ingestion pipeline.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Maximum characters per chunk (default: 1000)",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=200,
        help="Character overlap between chunks (default: 200)",
    )
    parser.add_argument(
        "--embedding-model",
        type=str,
        default=_DEFAULT_EMBED_MODEL,
        help=f"sentence-transformers model name (default: {_DEFAULT_EMBED_MODEL})",
    )
    parser.add_argument(
        "--text",
        type=str,
        default=None,
        help="Raw text to chunk and embed (for quick testing)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG-level logging",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: chunk and embed a text snippet or stdin."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    raw_text = args.text
    if raw_text is None:
        import sys
        if sys.stdin.isatty():
            parser.error("Provide --text or pipe content via stdin")
        raw_text = sys.stdin.read()

    doc = Document(page_content=raw_text, metadata={"source": "cli"})

    chunker = DocumentChunker(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        embedding_model=args.embedding_model,
    )
    results = chunker.process([doc])

    for i, chunk in enumerate(results):
        emb = chunk.metadata.get("embedding", [])
        print(
            f"Chunk {i}: {len(chunk.page_content)} chars, "
            f"embedding dim={len(emb)}"
        )


if __name__ == "__main__":
    main()
=======
>>>>>>> feature/retrieve

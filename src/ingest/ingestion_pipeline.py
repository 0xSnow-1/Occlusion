"""End-to-end data ingestion pipeline for Occlusion.

Composes the three ingestion stages into one runnable pipeline:

    1. Parse  -- `document_parser.load_all_documents` (local PDFs + web pages)
    2. Chunk  -- `DocumentChunker.chunk_documents` (RecursiveCharacterTextSplitter)
    3. Index  -- `VectorStore` (Qdrant hybrid collection, dense + sparse)

Dense and sparse embeddings are computed by fastembed at upsert time
(see DECISIONS/hybrid-qdrant-vector-store.md), so no separate embedding
step runs inside the pipeline.

Usage:
    uv run python -m src.ingest.ingestion_pipeline
"""

from __future__ import annotations

import logging

from src.ingest.chunking_and_embedding import DocumentChunker
from src.ingest.document_parser import load_all_documents
from src.ingest.vector_store import VectorStore

logger = logging.getLogger(__name__)

# -- Defaults -----------------------------------------------------------------

PDF_DIRECTORY = "data/raw"
COLLECTION_NAME = "occlusion"
QDRANT_STORAGE_PATH = "./data/qdrant_storage"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# The 11 HTML-only corpus sources (see data/HTML_SOURCES.md).
DEFAULT_HTML_URLS: list[str] = [
    "https://www.nidcr.nih.gov/health-info/gum-disease",
    "https://www.cdc.gov/oral-health/about/cavities-tooth-decay.html",
    "https://www.nhs.uk/tests-and-treatments/wisdom-tooth-removal/",
    "https://www.nhs.uk/tests-and-treatments/root-canal-treatment/",
    "https://www.nhs.uk/conditions/tooth-decay/",
    "https://www.nhs.uk/conditions/gum-disease/",
    "https://www.nhs.uk/symptoms/teeth-grinding/",
    "https://www.nhs.uk/conditions/dental-abscess/",
    "https://www.nhs.uk/conditions/knocked-out-tooth/",
    "https://www.nhs.uk/symptoms/toothache/",
    "https://www.nhs.uk/live-well/healthy-teeth-and-gums/dental-treatments/",
]


class IngestionPipeline:
    """Parse -> chunk -> index, in one call.

    Parameters
    ----------
    pdf_directory:
        Directory scanned recursively for PDFs.
    html_urls:
        Web pages to load. Defaults to the project corpus
        (``DEFAULT_HTML_URLS``); pass an empty list for PDFs only.
    collection_name:
        Qdrant collection to (re)create and fill.
    qdrant_path:
        Local Qdrant storage path. Pass an ``https://...`` URL to target
        Qdrant Cloud instead.
    chunk_size:
        Maximum character count per chunk (forwarded to ``DocumentChunker``).
    chunk_overlap:
        Character overlap between consecutive chunks.
    recreate_collection:
        When True (default) the collection is deleted and recreated on
        every run, so the store always mirrors the current corpus exactly
        and no stale points survive a re-ingest.
    """

    def __init__(
        self,
        pdf_directory: str = PDF_DIRECTORY,
        html_urls: list[str] | None = None,
        collection_name: str = COLLECTION_NAME,
        qdrant_path: str = QDRANT_STORAGE_PATH,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
        recreate_collection: bool = True,
    ) -> None:
        self.pdf_directory = pdf_directory
        self.html_urls = DEFAULT_HTML_URLS if html_urls is None else html_urls
        self.collection_name = collection_name
        self.recreate_collection = recreate_collection
        self._chunker = DocumentChunker(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )
        self._store = VectorStore(
            collection_name=collection_name, qdrant_url=qdrant_path
        )

    def run(self) -> dict[str, int]:
        """Execute the full pipeline and return per-stage counts.

        Returns
        -------
        dict with keys ``pages`` (pages parsed), ``chunks`` (chunks
        produced) and ``points`` (points upserted into Qdrant).
        """
        # Stage 1: parse ------------------------------------------------------
        documents = load_all_documents(self.pdf_directory, self.html_urls)
        if not documents:
            logger.warning("No documents found -- nothing to ingest.")
            return {"pages": 0, "chunks": 0, "points": 0}
        logger.info("Parsed %d pages", len(documents))

        # Stage 2: chunk ------------------------------------------------------
        # Embedding is deliberately NOT done here: fastembed embeds both the
        # dense and sparse vectors at upsert time (see module docstring).
        chunks = self._chunker.chunk_documents(documents)
        logger.info("Produced %d chunks", len(chunks))

        # Stage 3: index ------------------------------------------------------
        if self.recreate_collection and self._store.collection_exists():
            self._store.delete_collection()
        self._store.create_collection()
        points = self._store.upsert_documents(
            [{"text": chunk.page_content, **chunk.metadata} for chunk in chunks]
        )

        summary = {"pages": len(documents), "chunks": len(chunks), "points": points}
        logger.info("Ingestion complete: %s", summary)
        return summary


def main() -> None:
    """CLI entry point: ingest the full default corpus into local Qdrant storage."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    summary = IngestionPipeline().run()
    logger.info("Pipeline summary: %s", summary)


if __name__ == "__main__":
    main()

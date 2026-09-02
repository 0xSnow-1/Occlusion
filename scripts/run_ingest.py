"""End-to-end ingest pipeline: parse PDFs -> chunk -> create Qdrant collection -> upsert.

Usage:
    uv run python scripts/run_ingest.py
"""

from __future__ import annotations

import time
from pathlib import Path

from src.ingest.document_parser import load_all_PDFS
from src.ingest.chunking_and_embedding import DocumentChunker
from src.ingest.vector_store import VectorStore

# -- Config ------------------------------------------------------------------

PDF_DIR = "data/raw"
COLLECTION_NAME = "occlusion"

# -- Pipeline ----------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("  Occlusion Ingest Pipeline")
    print("=" * 60)

    # Step 1: Parse PDFs
    print(f"\n[1/4] Parsing PDFs from {PDF_DIR} ...")
    start = time.perf_counter()
    documents = load_all_PDFS(PDF_DIR)
    elapsed = time.perf_counter() - start
    print(f"       Loaded {len(documents)} pages in {elapsed:.1f}s")

    if not documents:
        print("       No documents found. Aborting.")
        return

    # Step 2: Chunk documents
    print("\n[2/4] Chunking documents ...")
    start = time.perf_counter()
    chunker = DocumentChunker(chunk_size=1000, chunk_overlap=200)
    chunks = chunker.chunk_documents(documents)
    elapsed = time.perf_counter() - start
    print(f"       Produced {len(chunks)} chunks in {elapsed:.1f}s")

    # Step 3: Create Qdrant collection
    print("\n[3/4] Creating Qdrant collection ...")
    store = VectorStore(collection_name=COLLECTION_NAME, qdrant_url=":memory:")
    start = time.perf_counter()
    store.create_collection()
    elapsed = time.perf_counter() - start
    print(f"       Collection '{COLLECTION_NAME}' ready in {elapsed:.1f}s")
    print(f"       Collection exists: {store.collection_exists()}")

    # Step 4: Upsert chunks
    print("\n[4/4] Upserting chunks (fastembed will embed on the fly) ...")
    docs_for_upsert = [
        {"text": chunk.page_content, **chunk.metadata}
        for chunk in chunks
    ]
    start = time.perf_counter()
    count = store.upsert_documents(docs_for_upsert)
    elapsed = time.perf_counter() - start
    print(f"       Upserted {count} points in {elapsed:.1f}s")

    # Summary
    print("\n" + "=" * 60)
    print("  Done!")
    print(f"  Collection : {COLLECTION_NAME}")
    print(f"  Points     : {count}")
    print(f"  Dense model: sentence-transformers/all-MiniLM-L6-v2 (384-dim, cosine)")
    print(f"  Sparse model: prithivida/Splade_PP_en_v1")
    print("=" * 60)


if __name__ == "__main__":
    main()

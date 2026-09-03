"""Tests for src/ingest/chunking_and_embedding.py (document chunking)."""

from __future__ import annotations

from typing import List

from langchain_core.documents import Document

from src.ingest.chunking_and_embedding import DocumentChunker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _doc(text: str, doc_id: str = "test-doc") -> Document:
    return Document(page_content=text, metadata={"doc_id": doc_id})


def _docs() -> List[Document]:
    return [
        _doc("First document about teeth.", doc_id="doc-1"),
        _doc("Second document about gums.", doc_id="doc-2"),
    ]


# ---------------------------------------------------------------------------
# Chunking tests
# ---------------------------------------------------------------------------

class TestChunking:
    """Verify document splitting behaviour."""

    def test_short_doc_produces_single_chunk(self):
        chunker = DocumentChunker(chunk_size=1000, chunk_overlap=0)
        docs = [_doc("Hello world")]
        chunks = chunker.chunk_documents(docs)
        assert len(chunks) == 1
        assert chunks[0].page_content == "Hello world"

    def test_long_doc_splits_into_multiple_chunks(self):
        chunker = DocumentChunker(chunk_size=50, chunk_overlap=0)
        long_text = "word " * 20  # 100 chars
        chunks = chunker.chunk_documents([_doc(long_text)])
        assert len(chunks) > 1

    def test_metadata_inherited_and_extended(self):
        chunker = DocumentChunker(chunk_size=50, chunk_overlap=0)
        long_text = "alpha beta gamma " * 10
        chunks = chunker.chunk_documents([_doc(long_text)])
        for chunk in chunks:
            assert "chunk_index" in chunk.metadata
            assert "chunk_total" in chunk.metadata

    def test_chunk_index_is_sequential(self):
        chunker = DocumentChunker(chunk_size=50, chunk_overlap=0)
        long_text = "word " * 30
        chunks = chunker.chunk_documents([_doc(long_text)])
        indices = [c.metadata["chunk_index"] for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_chunk_total_matches_count(self):
        chunker = DocumentChunker(chunk_size=50, chunk_overlap=0)
        long_text = "word " * 30
        chunks = chunker.chunk_documents([_doc(long_text)])
        for chunk in chunks:
            assert chunk.metadata["chunk_total"] == len(chunks)

    def test_empty_input_returns_empty(self):
        chunker = DocumentChunker()
        assert chunker.chunk_documents([]) == []

    def test_multiple_docs_each_chunked(self):
        chunker = DocumentChunker(chunk_size=50, chunk_overlap=0)
        docs = [_doc("word " * 30, doc_id="a"), _doc("word " * 30, doc_id="b")]
        chunks = chunker.chunk_documents(docs)
        ids = {c.metadata["doc_id"] for c in chunks}
        assert ids == {"a", "b"}

    def test_overlap_produces_overlapping_text(self):
        chunker = DocumentChunker(chunk_size=30, chunk_overlap=10)
        text = "abcdefghij" * 5  # 50 chars
        chunks = chunker.chunk_documents([_doc(text)])
        if len(chunks) >= 2:
            tail = chunks[0].page_content[-10:]
            head = chunks[1].page_content[:10]
            assert tail in chunks[1].page_content or head in chunks[0].page_content


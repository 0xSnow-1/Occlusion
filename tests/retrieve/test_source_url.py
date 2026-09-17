"""Blocker 6 (B3): fresh ingest yields non-empty `source_url`.

Covers one PDF fixture plus one HTML fixture through
`src.ingest.document_parser`, then through chunking into
`points_to_chunks`, asserting `RetrievedChunk.source_url` is non-empty.
The frozen eval snapshot is deliberately left untouched — only the
ingest path is fixed here.
"""

from __future__ import annotations

from langchain_core.documents import Document

from src.agent.schemas import RetrievedChunk
from src.ingest import document_parser
from src.retrieve.base import points_to_chunks

PDF_TEXT = "Brush twice a day with fluoride toothpaste. " * 20
HTML_TEXT = "NHS guidance on treating a dental abscess promptly. " * 20
HTML_URL = "https://www.nhs.uk/conditions/dental-abscess/"


def _write_pdf(path) -> None:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), PDF_TEXT)
    doc.save(str(path))
    doc.close()


class _FakeWebLoader:
    """Stand-in for WebBaseLoader: no network, loader-native metadata."""

    def __init__(self, web_path=None, **kwargs):
        self.web_path = web_path

    def load(self):
        return [
            Document(
                page_content=HTML_TEXT,
                metadata={"source": self.web_path},
            )
        ]


class TestFreshIngestSourceUrl:
    def test_pdf_pages_carry_source_url(self, tmp_path):
        _write_pdf(tmp_path / "gum-disease.pdf")

        docs = document_parser.load_all_PDFS(str(tmp_path))

        assert docs, "expected at least one parsed PDF page"
        for doc in docs:
            assert doc.metadata.get("source_url"), (
                f"PDF page missing source_url: {doc.metadata}"
            )

    def test_html_pages_carry_page_url(self, monkeypatch):
        monkeypatch.setattr(
            document_parser, "WebBaseLoader", _FakeWebLoader
        )

        docs = document_parser.load_all_websites([HTML_URL])

        assert docs, "expected at least one parsed HTML page"
        for doc in docs:
            assert doc.metadata.get("source_url") == HTML_URL

    def test_chunks_map_to_non_empty_source_url(self, tmp_path, monkeypatch):
        _write_pdf(tmp_path / "gum-disease.pdf")
        monkeypatch.setattr(
            document_parser, "WebBaseLoader", _FakeWebLoader
        )

        pdf_docs = document_parser.load_all_PDFS(str(tmp_path))
        html_docs = document_parser.load_all_websites([HTML_URL])

        from src.ingest.chunking_and_embedding import DocumentChunker

        chunks = DocumentChunker().chunk_documents(pdf_docs + html_docs)
        assert chunks, "expected chunks from PDF + HTML fixtures"

        points = [
            {"id": i, "payload": {"text": c.page_content, **c.metadata}}
            for i, c in enumerate(chunks)
        ]
        retrieved: list[RetrievedChunk] = points_to_chunks(points)

        assert len(retrieved) == len(chunks)
        for chunk in retrieved:
            assert chunk.source_url, (
                f"chunk {chunk.doc_id!r} has empty source_url"
            )


class TestLegacyPayloadFallback:
    """Pre-`source_url` payloads still resolve via `file_path`/`source`."""

    def test_source_url_preferred(self):
        (chunk,) = points_to_chunks(
            [
                {
                    "id": 0,
                    "payload": {
                        "text": "t",
                        "doc_id": "d",
                        "source_url": "https://example.com/page",
                        "source": "https://example.com/other",
                    },
                }
            ]
        )
        assert chunk.source_url == "https://example.com/page"

    def test_loader_source_fallback(self):
        (chunk,) = points_to_chunks(
            [
                {
                    "id": 0,
                    "payload": {
                        "text": "t",
                        "doc_id": "d",
                        "source": "https://www.nhs.uk/conditions/gum-disease/",
                    },
                }
            ]
        )
        assert chunk.source_url == "https://www.nhs.uk/conditions/gum-disease/"

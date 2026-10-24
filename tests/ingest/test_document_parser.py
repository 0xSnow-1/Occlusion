"""Provenance contract for local PDF ingestion."""

from __future__ import annotations

from src.ingest.document_parser import APPROVED_PDF_PATHS, load_all_PDFS

PDF_TEXT = "Brush twice a day with fluoride toothpaste. " * 20


def _write_pdf(path) -> None:
    import pymupdf

    path.parent.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), PDF_TEXT)
    doc.save(str(path))
    doc.close()


def test_only_allowlisted_pdfs_are_loaded(tmp_path):
    _write_pdf(tmp_path / "flossing-brushing.pdf")
    _write_pdf(tmp_path / "not-approved.pdf")
    _write_pdf(tmp_path / "_archive" / "Uniform-Glossary-01-2020.pdf")

    docs = load_all_PDFS(str(tmp_path), APPROVED_PDF_PATHS)

    assert {doc.metadata["doc_id"] for doc in docs} == {"flossing-brushing"}


def test_archive_copy_of_approved_name_is_not_loaded(tmp_path):
    _write_pdf(tmp_path / "_archive" / "flossing-brushing.pdf")

    docs = load_all_PDFS(str(tmp_path), APPROVED_PDF_PATHS)

    assert docs == []


def test_no_allowlist_keeps_low_level_parser_backwards_compatible(tmp_path):
    _write_pdf(tmp_path / "any.pdf")

    docs = load_all_PDFS(str(tmp_path))

    assert docs
    assert {doc.metadata["doc_id"] for doc in docs} == {"any"}

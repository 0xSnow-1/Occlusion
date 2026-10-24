from pathlib import Path
import logging
from typing import List, Any
from langchain_community.document_loaders import PyMuPDFLoader, WebBaseLoader
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# Provenance allowlist (data/PROVENANCE.md): only these PDFs may enter the
# corpus. Paths are relative to PDFS_directory so a rejected file cannot be
# smuggled in through a subdirectory such as data/raw/_archive/.
APPROVED_PDF_PATHS: frozenset[str] = frozenset(
    {
        "dry-mouth.pdf",
        "flossing-brushing.pdf",
        "older-adults-and-oral-health.pdf",
        "regular-oral-health-care-keeps-you-healthy.pdf",
    }
)


def load_all_PDFS(
    PDFS_directory: str,
    allowed_paths: frozenset[str] | set[str] | None = None,
) -> List[Any]:
    PDF_path = Path(PDFS_directory).resolve()
    logger.info(f"The Data Directory has been found: {PDF_path}")
    documents = []

    pdf_files = sorted(PDF_path.glob("**/*.pdf"))
    if allowed_paths is not None:
        pdf_files = [
            pdf_file
            for pdf_file in pdf_files
            if pdf_file.relative_to(PDF_path).as_posix() in allowed_paths
        ]
    logger.debug(
        f"There is a total number of {len(pdf_files)} PDF files for: {[str(f) for f in pdf_files]} "
    )
    for pdf_file in pdf_files:
        logger.info(f"Selected PDF file: {pdf_file}")

        try:
            loader = PyMuPDFLoader(str(pdf_file))
            loaded = loader.load()
            doc_id = pdf_file.stem
            for doc in loaded:
                doc.metadata["doc_id"] = doc_id
                # Blockers 6 (B3): carry the file path so fresh-ingest
                # payloads yield a non-empty RetrievedChunk.source_url.
                # PyMuPDFLoader already sets metadata["source"]; keep both.
                doc.metadata.setdefault("file_path", str(pdf_file))
                doc.metadata.setdefault("source_url", str(pdf_file))
            logger.debug(f"Assigned doc_id={doc_id} to {len(loaded)} pages")
            logger.info(f"Loaded {len(loaded)} pages from: {pdf_file}")
            documents.extend(loaded)
        except Exception as e:
            logger.exception(
                f"failed to parse and load pdf: {pdf_file}: {e}", exc_info=True
            )

    logger.info(f"Successfully Loaded {len(documents)} total pages.")
    return documents


def load_all_websites(URL_links: list[str]) -> List[Any]:
    logger.info(f"Found {len(URL_links)} websites..")
    documents = []

    for link in URL_links:
        logger.info(f"Selected file: {link}")

        try:
            loader = WebBaseLoader(web_path=link)
            loaded = loader.load()
            doc_id = link.split("/")[-2] or link.split("/")[-1]
            for doc in loaded:
                doc.metadata["doc_id"] = doc_id
                # Blocker 6 (B3): the real page URL is the source link.
                # WebBaseLoader sets metadata["source"]; source_url is the
                # canonical key the retriever and UI read.
                doc.metadata["source_url"] = link
                doc.metadata.setdefault("title", doc_id)
            logger.info(f"Loaded {len(loaded)} file for {link}")
            documents.extend(loaded)
        except Exception as e:
            logger.exception(f"Failed to parse website: {link}: {e}", exc_info=True)

    logger.info(f"Successfully Loaded {len(documents)} total site pages")
    return documents

def load_all_documents(
    PDFS_directory: str,
    URL_links: list[str],
    allowed_pdf_paths: frozenset[str] | set[str] | None = None,
) -> List[Document]:
    pdf_parser = load_all_PDFS(PDFS_directory, allowed_pdf_paths)
    html_parser = load_all_websites(URL_links)
    all_documents = pdf_parser + html_parser
    logger.info(f"Total documents loaded: {len(all_documents)}")
    return all_documents


__all__ = [
    "APPROVED_PDF_PATHS",
    "load_all_PDFS",
    "load_all_documents",
    "load_all_websites",
]


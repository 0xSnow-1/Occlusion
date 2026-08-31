from pathlib import Path
import logging
from typing import List, Any
from langchain_community.document_loaders import PyMuPDFLoader, WebBaseLoader
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


def load_all_PDFS(PDFS_directory: str) -> List[Any]:
    PDF_path = Path(PDFS_directory).resolve()
    logger.info(f"The Data Directory has been found: {PDF_path}")
    documents = []

    pdf_files = list(PDF_path.glob("**/*.pdf"))
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
            logger.info(f"Loaded {len(loaded)} file for {link}")
            documents.extend(loaded)
        except Exception as e:
            logger.exception(f"Failed to parse website: {link}: {e}", exc_info=True)

    logger.info(f"Successfully Loaded {len(documents)} total site pages")
    return documents


def load_all_documents(PDFS_directory: str, URL_links: list[str]) -> List[Document]:
    pdf_parser = load_all_PDFS(PDFS_directory)
    html_parser = load_all_websites(URL_links)
    all_documents = pdf_parser + html_parser
    logger.info(f"Total documents loaded: {len(all_documents)}")
    return all_documents


if __name__ == "__main__":
    HTML_URLS = [
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
    logging.basicConfig(level=logging.DEBUG)
    load_all_documents("data/raw", HTML_URLS)

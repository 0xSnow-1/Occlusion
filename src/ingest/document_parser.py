from pathlib import Path
import logging
from typing import List
from langchain_community.document_loaders import (
    PyMuPDFLoader,
)
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


def load_all_documents(data_directory: str) -> List[Document]:
    data_path = Path(data_directory).resolve()
    if not data_path.is_dir():
        raise FileNotFoundError(
            f"Document directory does not exist or is not a directory: {data_directory}"
        )
    logger.info(f"The Data Directory has been found: {data_path}")
    documents = []

    pdf_files = list(data_path.glob("**/*.pdf"))
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    load_all_documents("data/raw")

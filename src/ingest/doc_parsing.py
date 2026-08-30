import logging
from pathlib import Path

from docling.datamodel.base_models import ConversionStatus
from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

SUFFIX_COMPATIBLE = [".pdf", ".html", ".txt", ".docx"]


# 1. find the documents
# 2. Validate the documents
def parse_folder(folder: str) -> list[Document]:
    converter = DocumentConverter()
    chunker = HybridChunker()
    documents = []

    folder_path = Path(folder)
    if not folder_path.is_dir():
        raise FileNotFoundError(
            f"Document folder does not exist or is not a directory: {folder}"
        )

    for file in folder_path.rglob("*"):
        if not file.is_file():
            continue
        if file.suffix.lower() not in SUFFIX_COMPATIBLE:
            continue

        try:
            result = converter.convert(file)
        except Exception:
            logger.exception("Failed to convert %s; skipping file", file)
            continue

        if result.status in (ConversionStatus.FAILURE, ConversionStatus.PARTIAL_SUCCESS):
            logger.warning(
                "Skipping %s: conversion finished with status %s",
                file,
                result.status,
            )
            continue

        docling_document = result.document

        chunks = chunker.chunk(docling_document)

        for chunk in chunks:
            metadata = chunk.meta.export_json_dict()

            documents.append(
                Document(
                    page_content=chunk.text,
                    metadata={
                        "source": str(file),
                        "file_type": file.suffix.lower(),
                        "file_name": file.name,
                        "docling_metadata": metadata,
                    },
                )
            )
    return documents


if __name__ == "__main__":
    documents = parse_folder("data/raw")

    for i, doc in enumerate(documents[:5]):
        print(f"\n--- CHUNK {i} ---")
        print("TEXT:")
        print(doc.page_content[:200])
        print("\nMETADATA:")
        print(doc.metadata)

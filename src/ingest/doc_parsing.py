from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker

print("HybridChunker successfully imported!")
from pathlib import Path
from langchain_core.documents import Document


SUFFIX_COMPATIBLE = [".pdf", ".html", ".txt", ".docx"]


# 1. find the documents
# 2. Validate the documents
# 3.
def parse_folder(folder: str) -> list[Document]:
    converter = DocumentConverter()
    chunker = HybridChunker()
    documents = []

    for file in Path(folder).rglob("*"):
        if not file.is_file():
            continue
        if file.suffix.lower() not in SUFFIX_COMPATIBLE:
            continue

        result = converter.convert(file)
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


documents = parse_folder Path("data/raw")

for i, doc in enumerate(documents[:5]):
    print(f"\n--- CHUNK {i} ---")
    print("TEXT:")
    print(doc.page_content[:200])
    print("\nMETADATA:")
    print(doc.metadata)

from pathlib import Path
from typing import List, Any
from langchain_community.document_loaders import (
    PyMuPDFLoader,
    PyPDFLoader,
    TextLoader,
    CSVLoader,
    pdf,
)
from langchain_community.document_loaders import Docx2txtLoader
from langchain_community.document_loaders.excel import UnstructuredExcelLoader
from langchain_community.document_loaders import JSONLoader


def load_all_documents(data_directory: str) -> list[Any]:
    data_path = Path(data_directory).resolve()
    print(f"[DEBUG]: Data directory: {data_path}")
    documents = []

    pdf_files = list(data_path.glob("**/.pdf"))
    print(
        f"[DEBUG]: There is a total number of {len(pdf_files)} PDF files: {[str(f) for f in pdf_files]}"
    )
    for pdf_file in pdf_files:
        print(f"Loading PDF: {pdf_file}")
        try:
            loader = PyMuPDFLoader(str(pdf_file))
            loaded = loader.load()
            print(f"Loaded Pages: {len(loaded)} from PDF: {pdf_file}")
            documents.extend(loaded)
        except Exception as e:
            print(f"[ERROR]: Failed to Parse and Load PDF: {pdf_file}: {str(e)}")

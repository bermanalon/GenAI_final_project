"""
Offline embedding script for the job-description PDF.

Purpose:
- Load the PDF
- Split it into chunks
- Create embeddings
- Store them in a local Chroma database

Run this script manually whenever you want to rebuild the vector DB.
"""

from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv
import os

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PDF_PATH = PROJECT_ROOT / "Python Developer Job Description.pdf"
CHROMA_DIR = PROJECT_ROOT / "data" / "chroma_jobs"
COLLECTION_NAME = "python_job_description"


def load_pdf(pdf_path: Path):
    loader = PyPDFLoader(str(pdf_path))
    documents = loader.load()
    return documents


def split_documents(documents):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
    )
    return splitter.split_documents(documents)


def build_vector_db(chunks):
    embeddings = OpenAIEmbeddings()
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(CHROMA_DIR),
        collection_name=COLLECTION_NAME,
    )
    return vectorstore


def main():
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"PDF not found: {PDF_PATH}")

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading PDF: {PDF_PATH}")
    documents = load_pdf(PDF_PATH)
    print(f"Loaded {len(documents)} pages")

    chunks = split_documents(documents)
    print(f"Created {len(chunks)} chunks")

    build_vector_db(chunks)
    print(f"Chroma DB created at: {CHROMA_DIR}")
    print("Done.")


if __name__ == "__main__":
    main()
"""
Simple retriever helper for the Info Advisor.

Purpose:
- Open the existing Chroma DB
- Retrieve top matching chunks for a user question
- Return the chunk text in a simple format
"""

from pathlib import Path
from dotenv import load_dotenv

from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma


load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHROMA_DIR = PROJECT_ROOT / "data" / "chroma_jobs"
COLLECTION_NAME = "python_job_description"


def get_vectorstore():
    embeddings = OpenAIEmbeddings()

    return Chroma(
        persist_directory=str(CHROMA_DIR),
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
    )


def retrieve_job_context(query, k=3):
    vectorstore = get_vectorstore()
    results = vectorstore.similarity_search(query, k=k)

    chunks = []
    for doc in results:
        text = doc.page_content.strip()
        if text:
            chunks.append(text)

    return chunks


def build_context_text(query, k=3):
    chunks = retrieve_job_context(query=query, k=k)

    if not chunks:
        return ""

    return "\n\n---\n\n".join(chunks)
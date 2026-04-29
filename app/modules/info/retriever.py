"""
In-memory retriever helper (pure notebook-style, no LangChain).

- Read PDF using pypdf
- Split text manually into chunks
- Create embeddings with OpenAI (text-embedding-3-small)
- Store in in-memory Chroma
- Query with embeddings
"""

from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
import chromadb
from pypdf import PdfReader


load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PDF_PATH = PROJECT_ROOT / "Python Developer Job Description.pdf"

COLLECTION_NAME = "python_job_description"
EMBEDDING_MODEL = "text-embedding-3-small"

_collection = None


# -----------------------------
# PDF → text
# -----------------------------
def load_pdf_text():
    reader = PdfReader(str(PDF_PATH))

    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"

    return text


# -----------------------------
# Simple chunking
# -----------------------------
def split_text(text, chunk_size=500, overlap=100):
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk.strip())
        start += (chunk_size - overlap)

    return chunks


# -----------------------------
# Embeddings
# -----------------------------
def create_embeddings(texts):
    client = OpenAI()

    response = client.embeddings.create(
        input=texts,
        model=EMBEDDING_MODEL,
    )

    return [item.embedding for item in response.data]


# -----------------------------
# Build in-memory Chroma
# -----------------------------
def build_collection():
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"PDF not found: {PDF_PATH}")

    full_text = load_pdf_text()
    chunks = split_text(full_text)

    ids = [f"chunk_{i}" for i in range(len(chunks))]

    embeddings = create_embeddings(chunks)

    chroma_client = chromadb.Client()

    collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME
    )

    collection.add(
        documents=chunks,
        embeddings=embeddings,
        ids=ids,
    )

    return collection


def get_collection():
    global _collection

    if _collection is None:
        _collection = build_collection()

    return _collection


# -----------------------------
# Retrieval
# -----------------------------
def retrieve_job_context(query, k=3):
    collection = get_collection()

    query_embedding = create_embeddings([query])[0]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
    )

    documents = results.get("documents", [[]])[0]

    return [doc.strip() for doc in documents if doc.strip()]


def build_context_text(query, k=3):
    chunks = retrieve_job_context(query, k=k)

    if not chunks:
        return ""

    return "\n\n---\n\n".join(chunks)
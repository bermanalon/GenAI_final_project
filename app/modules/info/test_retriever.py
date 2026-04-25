"""
Small retrieval test for the job-description Chroma DB.

Purpose:
- Open the existing Chroma DB
- Query it with a sample question
- Print the top matching chunks
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


def main():
    vectorstore = get_vectorstore()

    query = "What experience is required for this position?"
    results = vectorstore.similarity_search(query, k=3)

    print(f"\nQuery: {query}\n")
    print(f"Returned {len(results)} results\n")

    for i, doc in enumerate(results, start=1):
        print("=" * 80)
        print(f"RESULT {i}")
        print("Metadata:", doc.metadata)
        print()
        print(doc.page_content)
        print()


if __name__ == "__main__":
    main()
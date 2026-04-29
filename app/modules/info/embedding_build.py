"""
Optional demo script for testing PDF embedding and retrieval.

The actual app uses app/modules/info/retriever.py.

This file is only for manual testing and learning.
It follows the notebook-style approach:
- OpenAI() directly
- client.embeddings.create(...)
- chromadb.Client()
- collection.add(...)
- collection.query(...)
"""

from app.modules.info.retriever import build_context_text


def main():
    query = "What experience is required for this position?"

    print("Query:")
    print(query)

    print("\nRetrieved context:")
    print(build_context_text(query, k=3))


if __name__ == "__main__":
    main()
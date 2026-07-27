"""
F2 — Ingestion + vector store.

Loads documents, chunks them, embeds them with OpenAI, and stores them in
Qdrant. This has to exist and be populated before the retriever agent (F3)
can return anything — so it's the second thing built, right after F1.

Done when: running `python -m app.core.ingestion` populates the collection,
and a similarity search for a known phrase returns the relevant chunk.
"""
import glob
import os
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

from app.core.config import get_embeddings, settings

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")


def load_documents(data_dir: str = DATA_DIR) -> List[Document]:
    """Load every .txt/.md file in data_dir into LangChain Documents."""
    docs: List[Document] = []
    for path in glob.glob(os.path.join(data_dir, "**", "*.*"), recursive=True):
        if not path.lower().endswith((".txt", ".md")):
            continue
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        docs.append(Document(page_content=text, metadata={"source": os.path.basename(path)}))
    return docs


def chunk_documents(docs: List[Document], chunk_size: int = 800, chunk_overlap: int = 120) -> List[Document]:
    """Word-boundary-aware chunking (same approach as the earlier RAG project)."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(docs)


def get_qdrant_client() -> QdrantClient:
    """Cloud Qdrant if QDRANT_URL is set, otherwise a local embedded instance (no signup)."""
    if settings.QDRANT_URL:
        return QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None)
    return QdrantClient(path=os.path.join(DATA_DIR, "qdrant_local"))


def ensure_collection(client: QdrantClient, name: str, vector_size: int = 1536) -> None:
    existing = [c.name for c in client.get_collections().collections]
    if name not in existing:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )


def build_vector_store(collection_name: str = None) -> QdrantVectorStore:
    """Return a QdrantVectorStore ready for similarity_search / add_documents."""
    collection_name = collection_name or settings.QDRANT_COLLECTION
    client = get_qdrant_client()
    ensure_collection(client, collection_name)
    return QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=get_embeddings(),
    )


def ingest() -> int:
    """Load -> chunk -> embed -> upsert. Returns the number of chunks ingested."""
    docs = load_documents()
    if not docs:
        print(f"No .txt/.md files found in {DATA_DIR} — add source documents there first.")
        return 0

    chunks = chunk_documents(docs)
    store = build_vector_store()
    store.add_documents(chunks)
    print(f"Ingested {len(chunks)} chunks from {len(docs)} documents into "
          f"'{settings.QDRANT_COLLECTION}'.")
    return len(chunks)


if __name__ == "__main__":
    settings.validate()
    ingest()

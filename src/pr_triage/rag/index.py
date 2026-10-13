import os

import chromadb
from dotenv import load_dotenv
from openai import OpenAI

from pr_triage.rag.chunking import load_chunks

load_dotenv()

CHROMA_DIR = "data/chroma"
COLLECTION_NAME = "policies"
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


def embed(texts: list[str], client: OpenAI) -> list[list[float]]:
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def get_collection():
    chroma = chromadb.PersistentClient(path=CHROMA_DIR)
    return chroma.get_or_create_collection(
        name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )


def build_index(client: OpenAI) -> int:
    collection = get_collection()
    existing_ids = collection.get()["ids"]
    if existing_ids:
        collection.delete(ids=existing_ids)

    chunks = load_chunks()
    collection.add(
        ids=[c.chunk_id for c in chunks],
        documents=[c.text for c in chunks],
        embeddings=embed([c.text for c in chunks], client),
        metadatas=[
            {
                "source": c.source,
                "document": c.document,
                "clause": c.clause,
                "title": c.title,
                "effective_date": c.effective_date or "",
            }
            for c in chunks
        ],
    )
    return collection.count()
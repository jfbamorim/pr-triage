import os
import time

import chromadb
from dotenv import load_dotenv
from openai import OpenAI

from pr_triage.domain.schemas import LLMCall
from pr_triage.rag.chunking import load_chunks

load_dotenv()

CHROMA_DIR = "data/chroma"
COLLECTION_NAME = "policies"
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


def embed(
    texts: list[str], client: OpenAI, calls: list[LLMCall] | None = None
) -> list[list[float]]:
    start = time.perf_counter()
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    if calls is not None:
        calls.append(
            LLMCall(
                step="embedding",
                model=EMBEDDING_MODEL,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=0,
                latency=time.perf_counter() - start,
            )
        )
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
                "amends": c.amends or "",
            }
            for c in chunks
        ],
    )
    return collection.count()
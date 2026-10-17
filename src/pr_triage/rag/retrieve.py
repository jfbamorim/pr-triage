from openai import OpenAI

from pr_triage.domain.schemas import Evidence, LLMCall
from pr_triage.rag.index import embed, get_collection


def _to_evidence(
    chunk_id: str, text: str, metadata: dict, score: float | None = None
) -> Evidence:
    return Evidence(
        chunk_id=chunk_id,
        source=metadata["source"],
        document=metadata["document"],
        clause=metadata["clause"],
        title=metadata["title"],
        effective_date=metadata["effective_date"] or None,
        text=text,
        score=score,
        amends=metadata.get("amends") or None,
    )


def retrieve(
    query: str,
    client: OpenAI,
    top_k: int = 8,
    calls: list[LLMCall] | None = None,
) -> list[Evidence]:
    result = get_collection().query(
        query_embeddings=embed([query], client, calls), n_results=top_k
    )
    return [
        _to_evidence(chunk_id, text, metadata, 1 - distance)
        for chunk_id, text, metadata, distance in zip(
            result["ids"][0],
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
        )
    ]


def fetch_by_id(chunk_id: str) -> Evidence:
    result = get_collection().get(ids=[chunk_id])
    return _to_evidence(
        result["ids"][0], result["documents"][0], result["metadatas"][0]
    )


def fetch_amending(chunk_id: str) -> list[Evidence]:
    result = get_collection().get(where={"amends": chunk_id})
    return [
        _to_evidence(found_id, text, metadata)
        for found_id, text, metadata in zip(
            result["ids"], result["documents"], result["metadatas"]
        )
    ]
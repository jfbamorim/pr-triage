from pr_triage.domain.schemas import Evidence


def validate_citations(cited_chunk_ids: list[str], evidence: list[Evidence]) -> bool:
    if not cited_chunk_ids:
        return False
    known = {item.chunk_id for item in evidence}
    return all(chunk_id in known for chunk_id in cited_chunk_ids)
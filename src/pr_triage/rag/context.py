from pr_triage.domain.band import Band
from pr_triage.domain.schemas import Evidence
from pr_triage.rag.retrieve import fetch_amending, fetch_by_id

MIN_SCORE = 0.52
MAX_CHUNKS = 6

TIER_CLAUSES = {
    Band.NO_BLOCKERS: "02-escaloes-e-cotacoes#2.1",
    Band.POLICY_TO_BE_VERIFIED: "02-escaloes-e-cotacoes#2.2",
    Band.HUMAN_ACTION: "02-escaloes-e-cotacoes#2.3",
}


def select_context(
    chunks: list[Evidence],
    min_score: float = MIN_SCORE,
    max_chunks: int = MAX_CHUNKS,
) -> list[Evidence]:
    passing = [c for c in chunks if c.score is not None and c.score >= min_score]
    return sorted(passing, key=lambda c: c.score, reverse=True)[:max_chunks]


def add_linked_clauses(chunks: list[Evidence]) -> list[Evidence]:
    result = list(chunks)
    known = {c.chunk_id for c in result}
    for chunk in chunks:
        linked = (
            [fetch_by_id(chunk.amends)]
            if chunk.amends
            else fetch_amending(chunk.chunk_id)
        )
        for extra in linked:
            if extra.chunk_id not in known:
                known.add(extra.chunk_id)
                result.append(extra)
    return result
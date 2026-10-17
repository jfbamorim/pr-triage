from pr_triage.domain.band import Band
from pr_triage.domain.schemas import Evidence, PurchaseRequest
from pr_triage.rag.retrieve import fetch_amending, fetch_by_id

MIN_SCORE = 0.52
MAX_CHUNKS = 6

TIER_CLAUSES = {
    Band.NO_BLOCKERS: "02-escaloes-e-cotacoes#2.1",
    Band.POLICY_TO_BE_VERIFIED: "02-escaloes-e-cotacoes#2.2",
    Band.HUMAN_ACTION: "02-escaloes-e-cotacoes#2.3",
}

URGENT_CLAUSE = "02-escaloes-e-cotacoes#2.4"
FRAMEWORK_CLAUSE = "03-fornecedores-e-categorias#3.2"


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


def add_request_clauses(
    chunks: list[Evidence], pr: PurchaseRequest, band: Band
) -> list[Evidence]:
    wanted = []
    if pr.is_urgent and band != Band.NO_BLOCKERS:
        wanted.append(URGENT_CLAUSE)
    if pr.mentions_framework_contract:
        wanted.append(FRAMEWORK_CLAUSE)
    known = {c.chunk_id for c in chunks}
    return chunks + [fetch_by_id(i) for i in wanted if i not in known]
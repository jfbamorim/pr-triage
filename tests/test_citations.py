from pr_triage.domain.citations import validate_citations
from pr_triage.domain.schemas import Evidence


def make_evidence(chunk_id: str) -> Evidence:
    return Evidence(
        chunk_id=chunk_id,
        source="politica.md",
        document="Política",
        clause="2.1",
        title="Título",
        effective_date=None,
        text="texto",
    )


EVIDENCE = [make_evidence("a"), make_evidence("b")]


def test_accepts_ids_present_in_evidence():
    assert validate_citations(["a"], EVIDENCE)
    assert validate_citations(["a", "b"], EVIDENCE)


def test_rejects_empty_citations():
    assert not validate_citations([], EVIDENCE)


def test_rejects_invented_id():
    assert not validate_citations(["c"], EVIDENCE)


def test_rejects_if_any_id_is_invented():
    assert not validate_citations(["a", "c"], EVIDENCE)
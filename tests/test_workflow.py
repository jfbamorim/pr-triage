import pytest

from pr_triage import workflow
from pr_triage.domain.band import Band
from pr_triage.domain.category import Category
from pr_triage.domain.followup import fallback_followup
from pr_triage.domain.schemas import (
    Evidence,
    InputScreening,
    LLMCall,
    PurchaseRequest,
    ResultSummary,
)
from pr_triage.domain.status import EscalationReason, Reason, Status

MISSING = object()

TIER_1 = "02-escaloes-e-cotacoes#2.1"
TIER_3 = "02-escaloes-e-cotacoes#2.3"
CLAUSE = "05-categorias-especificas#5.6"

OK_SCREENING = InputScreening(is_suspicious=False, reason="normal")
SUSPICIOUS = InputScreening(is_suspicious=True, reason="ordens ao sistema")
GOOD_SUMMARY = ResultSummary(text="Resumo.", cited_chunk_ids=[CLAUSE])
GOOD_QUESTION = "Podes indicar o valor e o centro de custo?"


def make_pr(**overrides) -> PurchaseRequest:
    values = {
        "item": "cadeiras",
        "quantity": 5,
        "estimated_value_eur": 800.0,
        "cost_center": "1500",
        "category": Category.FURNITURE,
        "is_urgent": False,
        "mentions_framework_contract": False,
    }
    return PurchaseRequest(**{**values, **overrides})


def blank(**overrides) -> PurchaseRequest:
    values = {
        "item": None,
        "quantity": None,
        "estimated_value_eur": None,
        "cost_center": None,
        "category": Category.OTHER,
        "is_urgent": False,
        "mentions_framework_contract": False,
    }
    return PurchaseRequest(**{**values, **overrides})


def evidence(chunk_id: str, score: float | None) -> Evidence:
    return Evidence(
        chunk_id=chunk_id,
        source="politica.md",
        document="Política",
        clause=chunk_id.split("#")[-1],
        title="Título",
        effective_date=None,
        text="texto",
        score=score,
    )


def install(
    monkeypatch,
    *,
    screening=MISSING,
    pr=None,
    retrieved=MISSING,
    summary=MISSING,
    followup=MISSING,
) -> list[str]:
    called: list[str] = []
    screening = OK_SCREENING if screening is MISSING else screening
    retrieved = [evidence(CLAUSE, 0.7)] if retrieved is MISSING else retrieved
    summary = GOOD_SUMMARY if summary is MISSING else summary
    followup = GOOD_QUESTION if followup is MISSING else followup

    def fake_screen(text, client, calls=None):
        called.append("screening")
        if calls is not None:
            calls.append(
                LLMCall(
                    step="screening",
                    model="fake",
                    input_tokens=1,
                    output_tokens=1,
                    latency=0.1,
                )
            )
        return screening

    def fake_extract(text, client, calls=None):
        called.append("extraction")
        return pr or make_pr()

    def fake_retrieve(query, client, top_k=8, calls=None):
        called.append("retrieve")
        if isinstance(retrieved, Exception):
            raise retrieved
        return retrieved

    def fake_fetch(chunk_id):
        return evidence(chunk_id, None)

    def fake_summarize(result, client, calls=None):
        called.append("summarize")
        if isinstance(summary, Exception):
            raise summary
        return summary

    def fake_followup(pr, missing, client, calls=None):
        called.append("followup")
        if isinstance(followup, Exception):
            raise followup
        return followup

    monkeypatch.setattr(workflow, "screen_input", fake_screen)
    monkeypatch.setattr(workflow, "extract_request", fake_extract)
    monkeypatch.setattr(workflow, "retrieve", fake_retrieve)
    monkeypatch.setattr(workflow, "add_linked_clauses", lambda chunks: chunks)
    monkeypatch.setattr(workflow, "add_request_clauses", lambda chunks, pr, band: chunks)
    monkeypatch.setattr(workflow, "fetch_by_id", fake_fetch)
    monkeypatch.setattr(workflow, "summarize_result", fake_summarize)
    monkeypatch.setattr(workflow, "write_followup", fake_followup)
    return called


def run(previous=None):
    return workflow.run_workflow("texto do pedido", None, previous)


def test_suspicious_text_is_rejected_before_extraction(monkeypatch):
    called = install(monkeypatch, screening=SUSPICIOUS)
    result = run()
    assert result.status == Status.REJECTED
    assert result.reason == Reason.SUSPICIOUS_ACTIVITY
    assert called == ["screening"]


def test_screening_failure_is_rejected(monkeypatch):
    called = install(monkeypatch, screening=None)
    result = run()
    assert result.status == Status.REJECTED
    assert result.reason == Reason.SUSPICIOUS_ACTIVITY
    assert called == ["screening"]


def test_invalid_data_is_rejected_before_policy(monkeypatch):
    called = install(monkeypatch, pr=make_pr(quantity=0))
    result = run()
    assert result.status == Status.REJECTED
    assert result.reason == Reason.INVALID_DATA
    assert result.invalid == ["quantity"]
    assert "retrieve" not in called
    assert "summarize" not in called


def test_missing_data_asks_the_model_question_and_stops(monkeypatch):
    called = install(
        monkeypatch, pr=make_pr(estimated_value_eur=None, cost_center=None)
    )
    result = run()
    assert result.status == Status.NEEDS_INFO
    assert result.missing == ["estimated_value_eur", "cost_center"]
    assert result.follow_up == GOOD_QUESTION
    assert "retrieve" not in called
    assert "summarize" not in called


def test_question_that_skips_a_missing_field_uses_fallback(monkeypatch):
    install(
        monkeypatch,
        pr=make_pr(estimated_value_eur=None, cost_center=None),
        followup="Olá, falta informação?",
    )
    result = run()
    assert result.follow_up == fallback_followup(result.missing)


def test_question_error_uses_fallback(monkeypatch):
    install(
        monkeypatch,
        pr=make_pr(estimated_value_eur=None, cost_center=None),
        followup=RuntimeError("boom"),
    )
    result = run()
    assert result.status == Status.NEEDS_INFO
    assert result.follow_up == fallback_followup(result.missing)


def test_no_question_for_a_complete_request(monkeypatch):
    called = install(monkeypatch)
    result = run()
    assert result.follow_up is None
    assert "followup" not in called


def test_previous_request_is_completed_by_the_new_message(monkeypatch):
    install(monkeypatch, pr=blank(cost_center="1500"))
    previous = make_pr(cost_center=None)
    result = run(previous)
    assert result.status == Status.VALID
    assert result.request.cost_center == "1500"
    assert result.request.item == "cadeiras"


def test_retrieval_error_escalates_to_a_person(monkeypatch):
    called = install(monkeypatch, retrieved=RuntimeError("chroma em baixo"))
    result = run()
    assert result.escalation == EscalationReason.RETRIEVAL_ERROR
    assert result.evidence == []
    assert result.summary is None
    assert "summarize" not in called


def test_no_relevant_clause_escalates_and_keeps_only_the_tier(monkeypatch):
    install(monkeypatch, retrieved=[evidence("outra#1.1", 0.30)])
    result = run()
    assert result.escalation == EscalationReason.NO_POLICY_EVIDENCE
    assert [e.chunk_id for e in result.evidence] == [TIER_1]


def test_value_over_threshold_escalates_with_the_top_tier_clause(monkeypatch):
    install(monkeypatch, pr=make_pr(estimated_value_eur=7000.0))
    result = run()
    assert result.band == Band.HUMAN_ACTION
    assert result.escalation == EscalationReason.OVER_THRESHOLD
    assert result.evidence[0].chunk_id == TIER_3


def test_invented_citation_discards_the_summary_but_keeps_the_decision(monkeypatch):
    install(
        monkeypatch,
        summary=ResultSummary(text="Resumo.", cited_chunk_ids=["inventado#9.9"]),
    )
    result = run()
    assert result.summary is None
    assert result.status == Status.VALID
    assert result.band == Band.NO_BLOCKERS
    assert result.escalation is None


def test_empty_citations_discard_the_summary(monkeypatch):
    install(monkeypatch, summary=ResultSummary(text="Resumo.", cited_chunk_ids=[]))
    assert run().summary is None


def test_summary_error_keeps_the_decision(monkeypatch):
    install(monkeypatch, summary=RuntimeError("timeout"))
    result = run()
    assert result.summary is None
    assert result.status == Status.VALID
    assert result.band == Band.NO_BLOCKERS


def test_valid_summary_is_kept_and_calls_are_attached(monkeypatch):
    install(monkeypatch)
    result = run()
    assert result.summary == GOOD_SUMMARY
    assert [call.step for call in result.calls] == ["screening"]
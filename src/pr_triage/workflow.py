from collections.abc import Iterator
from enum import Enum
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel

from pr_triage.domain.band import Band, determine_band
from pr_triage.domain.category import Category
from pr_triage.domain.citations import validate_citations
from pr_triage.domain.labels import (
    BAND_LABELS,
    ESCALATION_LABELS,
    FIELD_LABELS,
    format_eur,
)
from pr_triage.domain.merge import merge_requests
from pr_triage.domain.schemas import (
    Evidence,
    PurchaseRequest,
    ResultSummary,
    WorkflowResult,
)
from pr_triage.domain.status import EscalationReason, Reason, Status, determine_status
from pr_triage.domain.validation import validate_request
from pr_triage.llm.extract_purchase_request import extract_request
from pr_triage.llm.screen_input import screen_input
from pr_triage.llm.summarize_result import summarize_result
from pr_triage.rag.context import (
    TIER_CLAUSES,
    add_linked_clauses,
    add_request_clauses,
    select_context,
)
from pr_triage.rag.query import build_query
from pr_triage.rag.retrieve import fetch_by_id, retrieve


class Step(str, Enum):
    SCREENING = "screening"
    EXTRACTION = "extraction"
    VALIDATION = "validation"
    BAND = "band"
    POLICY = "policy"
    DECISION = "decision"
    SUMMARY = "summary"


class StepEvent(BaseModel):
    step: Step
    state: Literal["running", "done", "failed"]
    detail: str = ""


def _gather_evidence(
    pr: PurchaseRequest, band: Band, client: OpenAI
) -> tuple[list[Evidence], EscalationReason | None]:
    try:
        selected = add_linked_clauses(select_context(retrieve(build_query(pr), client)))
        clauses = add_request_clauses(selected, pr, band)
        tier = fetch_by_id(TIER_CLAUSES[band])
    except Exception:
        return [], EscalationReason.RETRIEVAL_ERROR

    evidence = [tier] + clauses
    if band == Band.HUMAN_ACTION:
        return evidence, EscalationReason.OVER_THRESHOLD
    if not selected:
        return evidence, EscalationReason.NO_POLICY_EVIDENCE
    return evidence, None


def _summarize(result: WorkflowResult, client: OpenAI) -> ResultSummary | None:
    if not result.evidence:
        return None
    try:
        summary = summarize_result(result, client)
    except Exception:
        return None
    if summary is None:
        return None
    if not validate_citations(summary.cited_chunk_ids, result.evidence):
        return None
    return summary


def _describe_request(pr: PurchaseRequest) -> str:
    quantity = pr.quantity if pr.quantity is not None else "—"
    return " · ".join(
        [
            str(pr.item) if pr.item else "—",
            f"quantidade {quantity}",
            f"valor {format_eur(pr.estimated_value_eur)}",
            f"centro de custo {pr.cost_center or '—'}",
        ]
    )


def iter_workflow(
    text: str, client: OpenAI, previous: PurchaseRequest | None = None
) -> Iterator[StepEvent | WorkflowResult]:
    yield StepEvent(step=Step.SCREENING, state="running")
    screening = screen_input(text, client)
    if screening is None or screening.is_suspicious:
        yield StepEvent(step=Step.SCREENING, state="failed", detail="Texto suspeito")
        yield WorkflowResult(status=Status.REJECTED, reason=Reason.SUSPICIOUS_ACTIVITY)
        return
    yield StepEvent(step=Step.SCREENING, state="done", detail="Texto normal")

    yield StepEvent(step=Step.EXTRACTION, state="running")
    pr = extract_request(text, client)
    if pr is None:
        pr = previous or PurchaseRequest(
            item=None,
            quantity=None,
            estimated_value_eur=None,
            cost_center=None,
            category=Category.OTHER,
            is_urgent=False,
            mentions_framework_contract=False,
        )
    elif previous is not None:
        pr = merge_requests(previous, pr)
    yield StepEvent(
        step=Step.EXTRACTION,
        state="done",
        detail=_describe_request(pr),
    )

    yield StepEvent(step=Step.VALIDATION, state="running")
    missing, invalid = validate_request(pr)
    status = determine_status(missing, invalid)
    if status == Status.REJECTED:
        yield StepEvent(
            step=Step.VALIDATION,
            state="failed",
            detail="Inválido: " + ", ".join(FIELD_LABELS[f] for f in invalid),
        )
        yield WorkflowResult(
            status=status,
            reason=Reason.INVALID_DATA,
            request=pr,
            missing=missing,
            invalid=invalid,
        )
        return
    if status == Status.NEEDS_INFO:
        yield StepEvent(
            step=Step.VALIDATION,
            state="failed",
            detail="Falta: " + ", ".join(FIELD_LABELS[f] for f in missing),
        )
        yield WorkflowResult(status=status, request=pr, missing=missing)
        return
    yield StepEvent(step=Step.VALIDATION, state="done", detail="Dados completos")

    yield StepEvent(step=Step.BAND, state="running")
    band = determine_band(pr.estimated_value_eur)
    yield StepEvent(step=Step.BAND, state="done", detail=BAND_LABELS[band])

    yield StepEvent(step=Step.POLICY, state="running")
    evidence, escalation = _gather_evidence(pr, band, client)
    if escalation in (
        EscalationReason.RETRIEVAL_ERROR,
        EscalationReason.NO_POLICY_EVIDENCE,
    ):
        yield StepEvent(
            step=Step.POLICY, state="failed", detail=ESCALATION_LABELS[escalation]
        )
    else:
        yield StepEvent(
            step=Step.POLICY, state="done", detail=f"{len(evidence)} cláusulas"
        )

    yield StepEvent(step=Step.DECISION, state="running")
    decision = (
        f"Ação manual: {ESCALATION_LABELS[escalation]}"
        if escalation
        else BAND_LABELS[band]
    )
    yield StepEvent(step=Step.DECISION, state="done", detail=decision)
    result = WorkflowResult(
        status=status,
        request=pr,
        band=band,
        escalation=escalation,
        evidence=evidence,
    )

    yield StepEvent(step=Step.SUMMARY, state="running")
    summary = _summarize(result, client)
    if summary is None:
        yield StepEvent(step=Step.SUMMARY, state="failed", detail="Resumo indisponível")
    else:
        count = len(summary.cited_chunk_ids)
        noun = "cláusula citada" if count == 1 else "cláusulas citadas"
        yield StepEvent(step=Step.SUMMARY, state="done", detail=f"{count} {noun}")
    yield result.model_copy(update={"summary": summary})


def run_workflow(
    text: str, client: OpenAI, previous: PurchaseRequest | None = None
) -> WorkflowResult:
    for event in iter_workflow(text, client, previous):
        if isinstance(event, WorkflowResult):
            return event
    raise RuntimeError("workflow ended without a result")
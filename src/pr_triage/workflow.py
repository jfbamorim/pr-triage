from collections.abc import Iterator
from enum import Enum
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel

from pr_triage.domain.band import Band, determine_band
from pr_triage.domain.merge import merge_requests
from pr_triage.domain.schemas import Evidence, PurchaseRequest, WorkflowResult
from pr_triage.domain.status import EscalationReason, Reason, Status, determine_status
from pr_triage.domain.validation import validate_request
from pr_triage.llm.extract_purchase_request import extract_request
from pr_triage.llm.screen_input import screen_input
from pr_triage.rag.context import TIER_CLAUSES, add_linked_clauses, select_context
from pr_triage.rag.query import build_query
from pr_triage.rag.retrieve import fetch_by_id, retrieve


class Step(str, Enum):
    SCREENING = "screening"
    EXTRACTION = "extraction"
    VALIDATION = "validation"
    BAND = "band"
    POLICY = "policy"
    DECISION = "decision"


class StepEvent(BaseModel):
    step: Step
    state: Literal["running", "done", "failed"]
    detail: str = ""


def _gather_evidence(
    pr: PurchaseRequest, band: Band, client: OpenAI
) -> tuple[list[Evidence], EscalationReason | None]:
    try:
        selected = add_linked_clauses(select_context(retrieve(build_query(pr), client)))
        tier = fetch_by_id(TIER_CLAUSES[band])
    except Exception:
        return [], EscalationReason.RETRIEVAL_ERROR

    evidence = [tier] + selected
    if band == Band.HUMAN_ACTION:
        return evidence, EscalationReason.OVER_THRESHOLD
    if not selected:
        return evidence, EscalationReason.NO_POLICY_EVIDENCE
    return evidence, None


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
            item=None, quantity=None, estimated_value_eur=None, cost_center=None
        )
    elif previous is not None:
        pr = merge_requests(previous, pr)
    yield StepEvent(
        step=Step.EXTRACTION,
        state="done",
        detail=(
            f"item={pr.item}, quantidade={pr.quantity}, "
            f"valor={pr.estimated_value_eur}, centro de custo={pr.cost_center}"
        ),
    )

    yield StepEvent(step=Step.VALIDATION, state="running")
    missing, invalid = validate_request(pr)
    status = determine_status(missing, invalid)
    if status == Status.REJECTED:
        yield StepEvent(
            step=Step.VALIDATION, state="failed", detail="Inválido: " + ", ".join(invalid)
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
            step=Step.VALIDATION, state="failed", detail="Falta: " + ", ".join(missing)
        )
        yield WorkflowResult(status=status, request=pr, missing=missing)
        return
    yield StepEvent(step=Step.VALIDATION, state="done", detail="Dados completos")

    yield StepEvent(step=Step.BAND, state="running")
    band = determine_band(pr.estimated_value_eur)
    yield StepEvent(step=Step.BAND, state="done", detail=band.value)

    yield StepEvent(step=Step.POLICY, state="running")
    evidence, escalation = _gather_evidence(pr, band, client)
    if escalation in (
        EscalationReason.RETRIEVAL_ERROR,
        EscalationReason.NO_POLICY_EVIDENCE,
    ):
        yield StepEvent(step=Step.POLICY, state="failed", detail=escalation.value)
    else:
        yield StepEvent(
            step=Step.POLICY, state="done", detail=f"{len(evidence)} cláusulas"
        )

    yield StepEvent(step=Step.DECISION, state="running")
    decision = f"ação manual ({escalation.value})" if escalation else band.value
    yield StepEvent(step=Step.DECISION, state="done", detail=decision)
    yield WorkflowResult(
        status=status,
        request=pr,
        band=band,
        escalation=escalation,
        evidence=evidence,
    )


def run_workflow(
    text: str, client: OpenAI, previous: PurchaseRequest | None = None
) -> WorkflowResult:
    for event in iter_workflow(text, client, previous):
        if isinstance(event, WorkflowResult):
            return event
    raise RuntimeError("workflow ended without a result")
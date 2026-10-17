from pydantic import BaseModel

from pr_triage.domain.band import Band
from pr_triage.domain.status import EscalationReason, Reason, Status


class PurchaseRequest(BaseModel):
    item: str | None
    quantity: int | None
    estimated_value_eur: float | None
    cost_center: str | None


class InputScreening(BaseModel):
    is_suspicious: bool
    reason: str


class Evidence(BaseModel):
    chunk_id: str
    source: str
    document: str
    clause: str
    title: str
    effective_date: str | None
    text: str
    score: float | None = None
    amends: str | None = None


class ResultSummary(BaseModel):
    text: str
    cited_chunk_ids: list[str]


class WorkflowResult(BaseModel):
    status: Status
    reason: Reason | None = None
    request: PurchaseRequest | None = None
    missing: list[str] = []
    invalid: list[str] = []
    band: Band | None = None
    escalation: EscalationReason | None = None
    evidence: list[Evidence] = []
    summary: ResultSummary | None = None
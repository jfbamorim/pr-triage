from pydantic import BaseModel

from pr_triage.domain.band import Band
from pr_triage.domain.status import Reason, Status


class PurchaseRequest(BaseModel):
    item: str | None
    quantity: int | None
    estimated_value_eur: float | None
    cost_center: str | None


class InputScreening(BaseModel):
    is_suspicious: bool
    reason: str


class WorkflowResult(BaseModel):
    status: Status
    reason: Reason | None = None
    request: PurchaseRequest | None = None
    missing: list[str] = []
    invalid: list[str] = []
    band: Band | None = None
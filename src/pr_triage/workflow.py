from pydantic import BaseModel

from pr_triage.band import Band, determine_band
from pr_triage.extract_purchase_request import extract_request
from pr_triage.schemas import PurchaseRequest
from pr_triage.screen_input import screen_input
from pr_triage.status import Reason, Status, determine_status
from pr_triage.validation import validate_request

ALL_FIELDS = ["item", "quantity", "estimated_value_eur", "cost_center"]


class WorkflowResult(BaseModel):
    status: Status
    reason: Reason | None = None
    request: PurchaseRequest | None = None
    missing: list[str] = []
    invalid: list[str] = []
    band: Band | None = None


def run_workflow(text, client) -> WorkflowResult:
    screening = screen_input(text, client)
    if screening is None or screening.is_suspicious:
        return WorkflowResult(
            status=Status.REJECTED, reason=Reason.SUSPICIOUS_ACTIVITY
        )

    pr = extract_request(text, client)
    if pr is None:
        return WorkflowResult(status=Status.NEEDS_INFO, missing=ALL_FIELDS)

    missing, invalid = validate_request(pr)
    status = determine_status(missing, invalid)

    if status == Status.REJECTED:
        return WorkflowResult(
            status=status,
            reason=Reason.INVALID_DATA,
            request=pr,
            missing=missing,
            invalid=invalid,
        )
    if status == Status.NEEDS_INFO:
        return WorkflowResult(status=status, request=pr, missing=missing)
    return WorkflowResult(
        status=status, request=pr, band=determine_band(pr.estimated_value_eur)
    )
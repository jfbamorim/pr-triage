from pr_triage.domain.band import determine_band
from pr_triage.domain.merge import merge_requests
from pr_triage.domain.schemas import PurchaseRequest, WorkflowResult
from pr_triage.domain.status import Reason, Status, determine_status
from pr_triage.domain.validation import validate_request
from pr_triage.llm.extract_purchase_request import extract_request
from pr_triage.llm.screen_input import screen_input


def run_workflow(
    text, client, previous: PurchaseRequest | None = None
) -> WorkflowResult:
    screening = screen_input(text, client)
    if screening is None or screening.is_suspicious:
        return WorkflowResult(
            status=Status.REJECTED, reason=Reason.SUSPICIOUS_ACTIVITY
        )

    pr = extract_request(text, client)
    if pr is None:
        pr = previous or PurchaseRequest(
            item=None, quantity=None, estimated_value_eur=None, cost_center=None
        )
    elif previous is not None:
        pr = merge_requests(previous, pr)

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
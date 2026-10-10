from pr_triage.domain.schemas import PurchaseRequest, WorkflowResult
from pr_triage.domain.status import Reason, Status
from pr_triage.storage.db import (
    create_request,
    get_request,
    init_db,
    update_request,
)
from pr_triage.workflow import run_workflow


def _open_request(request_id: int | None) -> PurchaseRequest | None:
    if request_id is None:
        return None
    row = get_request(request_id)
    if row is None or row["status"] != Status.NEEDS_INFO.value:
        return None
    return PurchaseRequest(
        item=row["item"],
        quantity=row["quantity"],
        estimated_value_eur=row["estimated_value_eur"],
        cost_center=row["cost_center"],
    )


def process_message(
    text, client, request_id: int | None = None
) -> tuple[int | None, WorkflowResult]:
    init_db()
    previous = _open_request(request_id)
    if previous is None:
        request_id = None

    result = run_workflow(text, client, previous)

    if result.reason == Reason.SUSPICIOUS_ACTIVITY:
        return request_id, result

    if request_id is None:
        request_id = create_request(result)
    else:
        update_request(request_id, result)
    return request_id, result
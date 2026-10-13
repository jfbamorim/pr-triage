from collections.abc import Iterator

from openai import OpenAI
from pydantic import BaseModel

from pr_triage.domain.schemas import PurchaseRequest, WorkflowResult
from pr_triage.domain.status import Reason, Status
from pr_triage.storage.db import (
    create_request,
    get_request,
    init_db,
    update_request,
)
from pr_triage.workflow import StepEvent, iter_workflow


class Outcome(BaseModel):
    request_id: int | None
    result: WorkflowResult


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


def iter_process_message(
    text: str, client: OpenAI, request_id: int | None = None
) -> Iterator[StepEvent | Outcome]:
    init_db()
    previous = _open_request(request_id)
    if previous is None:
        request_id = None

    result = None
    for event in iter_workflow(text, client, previous):
        if isinstance(event, WorkflowResult):
            result = event
        else:
            yield event

    if result.reason != Reason.SUSPICIOUS_ACTIVITY:
        if request_id is None:
            request_id = create_request(result)
        else:
            update_request(request_id, result)
    yield Outcome(request_id=request_id, result=result)


def process_message(
    text: str, client: OpenAI, request_id: int | None = None
) -> tuple[int | None, WorkflowResult]:
    for event in iter_process_message(text, client, request_id):
        if isinstance(event, Outcome):
            return event.request_id, event.result
    raise RuntimeError("service ended without an outcome")
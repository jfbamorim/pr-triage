import pytest

from pr_triage.domain.band import Band
from pr_triage.domain.category import Category
from pr_triage.domain.schemas import (
    Evidence,
    LLMCall,
    PurchaseRequest,
    ResultSummary,
    WorkflowResult,
)
from pr_triage.domain.status import Status
from pr_triage.storage import db


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()


def make_result(**overrides) -> WorkflowResult:
    values = {
        "status": Status.VALID,
        "request": PurchaseRequest(
            item="cadeiras",
            quantity=5,
            estimated_value_eur=800.0,
            cost_center="1500",
            category=Category.FURNITURE,
            is_urgent=True,
            mentions_framework_contract=False,
        ),
        "band": Band.NO_BLOCKERS,
        "evidence": [
            Evidence(
                chunk_id="02-escaloes-e-cotacoes#2.1",
                source="02.md",
                document="Escalões",
                clause="2.1",
                title="Abaixo de 1 000 €",
                effective_date=None,
                text="texto",
            )
        ],
        "summary": ResultSummary(
            text="Resumo.", cited_chunk_ids=["02-escaloes-e-cotacoes#2.1"]
        ),
        "calls": [
            LLMCall(
                step="summary",
                model="gpt-4.1-mini",
                prompt_version="summary-v3",
                input_tokens=700,
                output_tokens=120,
                latency=1.5,
            )
        ],
    }
    return WorkflowResult(**{**values, **overrides})


def test_full_result_is_stored_and_round_trips():
    result = make_result()
    request_id = db.create_request(result)
    row = db.get_request(request_id)
    assert WorkflowResult.model_validate_json(row["result_json"]) == result
    assert row["category"] == "furniture"
    assert row["is_urgent"] == 1


def test_update_replaces_the_stored_result():
    request_id = db.create_request(make_result(status=Status.NEEDS_INFO))
    updated = make_result()
    db.update_request(request_id, updated)
    row = db.get_request(request_id)
    assert row["status"] == "valid"
    assert WorkflowResult.model_validate_json(row["result_json"]) == updated
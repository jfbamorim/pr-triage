from pr_triage.domain.category import Category
from pr_triage.domain.schemas import PurchaseRequest
from pr_triage.domain.status import Status, determine_status
from pr_triage.domain.validation import validate_request


def make_request(**overrides) -> PurchaseRequest:
    values = {
        "item": "cadeira de escritório",
        "quantity": 1,
        "estimated_value_eur": 800.0,
        "cost_center": "1500",
        "category": Category.FURNITURE,
        "is_urgent": False,
        "mentions_framework_contract": False,
    }
    return PurchaseRequest(**{**values, **overrides})


def test_complete_request_has_no_missing_or_invalid():
    assert validate_request(make_request()) == ([], [])


def test_all_fields_missing():
    pr = make_request(
        item=None, quantity=None, estimated_value_eur=None, cost_center=None
    )
    missing, invalid = validate_request(pr)
    assert missing == ["item", "quantity", "estimated_value_eur", "cost_center"]
    assert invalid == []


def test_blank_strings_count_as_missing():
    missing, _ = validate_request(make_request(item="  ", cost_center=""))
    assert missing == ["item", "cost_center"]


def test_zero_or_negative_quantity_is_invalid():
    assert validate_request(make_request(quantity=0))[1] == ["quantity"]
    assert validate_request(make_request(quantity=-2))[1] == ["quantity"]


def test_zero_or_negative_value_is_invalid():
    assert validate_request(make_request(estimated_value_eur=0))[1] == [
        "estimated_value_eur"
    ]
    assert validate_request(make_request(estimated_value_eur=-50))[1] == [
        "estimated_value_eur"
    ]


def test_status_valid_when_nothing_wrong():
    assert determine_status([], []) == Status.VALID


def test_status_needs_info_when_something_missing():
    assert determine_status(["cost_center"], []) == Status.NEEDS_INFO


def test_status_rejected_when_invalid_even_if_something_missing():
    assert determine_status(["cost_center"], ["quantity"]) == Status.REJECTED
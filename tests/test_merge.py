from pr_triage.domain.category import Category
from pr_triage.domain.merge import merge_requests
from pr_triage.domain.schemas import PurchaseRequest


def make_request(**overrides) -> PurchaseRequest:
    values = {
        "item": None,
        "quantity": None,
        "estimated_value_eur": None,
        "cost_center": None,
        "category": Category.OTHER,
        "is_urgent": False,
        "mentions_framework_contract": False,
    }
    return PurchaseRequest(**{**values, **overrides})


def test_new_values_fill_missing_fields():
    old = make_request(item="cadeiras", quantity=3)
    new = make_request(estimated_value_eur=2500.0, cost_center="1500")
    merged = merge_requests(old, new)
    assert merged.item == "cadeiras"
    assert merged.quantity == 3
    assert merged.estimated_value_eur == 2500.0
    assert merged.cost_center == "1500"


def test_new_value_overrides_old():
    old = make_request(estimated_value_eur=800.0)
    new = make_request(estimated_value_eur=900.0)
    assert merge_requests(old, new).estimated_value_eur == 900.0


def test_none_does_not_erase_old_value():
    old = make_request(cost_center="1500")
    new = make_request(cost_center=None)
    assert merge_requests(old, new).cost_center == "1500"


def test_flags_stay_true_once_set():
    old = make_request(is_urgent=True, mentions_framework_contract=True)
    new = make_request()
    merged = merge_requests(old, new)
    assert merged.is_urgent
    assert merged.mentions_framework_contract


def test_flags_become_true_from_new_message():
    old = make_request()
    new = make_request(is_urgent=True)
    assert merge_requests(old, new).is_urgent


def test_category_other_keeps_old_category():
    old = make_request(category=Category.FURNITURE)
    new = make_request(category=Category.OTHER)
    assert merge_requests(old, new).category == Category.FURNITURE


def test_specific_category_replaces_other():
    old = make_request(category=Category.OTHER)
    new = make_request(category=Category.FURNITURE)
    assert merge_requests(old, new).category == Category.FURNITURE
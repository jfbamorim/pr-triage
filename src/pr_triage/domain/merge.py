from pr_triage.domain.category import Category
from pr_triage.domain.schemas import PurchaseRequest


def merge_requests(old: PurchaseRequest, new: PurchaseRequest) -> PurchaseRequest:
    merged = old.model_dump()
    merged.update(
        {
            k: v
            for k, v in new.model_dump().items()
            if v is not None and not isinstance(v, bool)
        }
    )
    merged["is_urgent"] = old.is_urgent or new.is_urgent
    merged["mentions_framework_contract"] = (
        old.mentions_framework_contract or new.mentions_framework_contract
    )
    if new.category == Category.OTHER:
        merged["category"] = old.category
    return PurchaseRequest(**merged)
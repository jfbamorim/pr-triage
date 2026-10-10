from pr_triage.domain.schemas import PurchaseRequest


def merge_requests(old: PurchaseRequest, new: PurchaseRequest) -> PurchaseRequest:
    merged = old.model_dump()
    merged.update({k: v for k, v in new.model_dump().items() if v is not None})
    return PurchaseRequest(**merged)
from pr_triage.domain.schemas import PurchaseRequest


def build_query(pr: PurchaseRequest) -> str:
    return f"Compra de {pr.item}"
from pr_triage.schemas import PurchaseRequest


def validate_request(pr: PurchaseRequest) -> tuple[list[str], list[str]]:
    missing = []
    invalid = []
    
    if pr.item is None or pr.item.strip() == "":
        missing.append("item")
    if pr.quantity is None:
        missing.append("quantity")
    elif pr.quantity <= 0:
        invalid.append("quantity")
    
    if pr.estimated_value_eur is None:
        missing.append("estimated_value_eur")
    elif pr.estimated_value_eur <= 0:
        invalid.append("estimated_value_eur")
    
    if pr.cost_center is None or pr.cost_center.strip() == "":
        missing.append("cost_center")
        
    return missing, invalid
        
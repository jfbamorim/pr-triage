from pydantic import BaseModel


class PurchaseRequest(BaseModel):
    item: str | None
    quantity: int | None
    estimated_value_eur: float | None
    cost_center: str | None
    
    
class InputScreening(BaseModel):
    is_suspicious: bool
    reason: str
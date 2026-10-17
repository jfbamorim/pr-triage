from pr_triage.domain.category import Category
from pr_triage.domain.schemas import PurchaseRequest

CATEGORY_TERMS = {
    Category.IT_EQUIPMENT: "equipamento informático",
    Category.FURNITURE: "mobiliário e material de escritório",
    Category.SERVICES: "serviços",
    Category.INVESTMENT_GOODS: "bens de investimento, equipamento de longa duração, aprovação do controlo de gestão",
    Category.MAINTENANCE: "manutenção",
    Category.LAB_CONSUMABLES: "consumíveis de laboratório",
    Category.CLEANING: "limpeza",
    Category.MARKETING: "marketing",
    Category.PACKAGING: "embalagens",
}


def build_query(pr: PurchaseRequest) -> str:
    term = CATEGORY_TERMS.get(pr.category)
    if term is None:
        return f"Compra de {pr.item}"
    return f"{term}: compra de {pr.item}"
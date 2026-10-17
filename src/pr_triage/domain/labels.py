from pr_triage.domain.band import Band
from pr_triage.domain.status import EscalationReason

BAND_LABELS = {
    Band.NO_BLOCKERS: "Sem bloqueios à aprovação direta",
    Band.POLICY_TO_BE_VERIFIED: "Política de compras a verificar",
    Band.HUMAN_ACTION: "Ação humana necessária",
}

ESCALATION_LABELS = {
    EscalationReason.OVER_THRESHOLD: "valor acima de 5 000 €",
    EscalationReason.NO_POLICY_EVIDENCE: "sem evidência na política",
    EscalationReason.RETRIEVAL_ERROR: "erro na consulta da política",
}

FIELD_LABELS = {
    "item": "item",
    "quantity": "quantidade",
    "estimated_value_eur": "valor estimado",
    "cost_center": "centro de custo",
}


def format_eur(value: float | None) -> str:
    if value is None:
        return "—"
    formatted = f"{value:,.2f}".replace(",", "\u00a0").replace(".", ",")
    return f"{formatted}\u00a0€"
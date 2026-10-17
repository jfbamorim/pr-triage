from pr_triage.domain.labels import FIELD_LABELS

KEYWORDS = {
    "item": "item",
    "quantity": "quantidade",
    "estimated_value_eur": "valor",
    "cost_center": "centro de custo",
}


def validate_followup(question: str | None, missing: list[str]) -> bool:
    if not question or not question.strip():
        return False
    text = question.lower()
    return all(KEYWORDS[field] in text for field in missing)


def fallback_followup(missing: list[str]) -> str:
    return "Falta indicar: " + ", ".join(FIELD_LABELS[f] for f in missing) + "."
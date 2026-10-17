from pr_triage.domain.followup import fallback_followup, validate_followup


def test_accepts_question_that_mentions_every_missing_field():
    question = "Podes indicar o valor e o centro de custo, por favor?"
    assert validate_followup(question, ["estimated_value_eur", "cost_center"])


def test_rejects_question_that_skips_a_missing_field():
    question = "Podes indicar o valor, por favor?"
    assert not validate_followup(question, ["estimated_value_eur", "cost_center"])


def test_rejects_empty_or_none():
    assert not validate_followup(None, ["item"])
    assert not validate_followup("   ", ["item"])


def test_matching_ignores_case():
    assert validate_followup("Qual é a QUANTIDADE?", ["quantity"])


def test_fallback_is_a_sentence_that_passes_nothing_extra():
    text = fallback_followup(["quantity", "cost_center"])
    assert text.startswith("Falta indicar:")
    assert text.endswith(".")
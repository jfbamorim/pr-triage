import html
from pathlib import Path

import streamlit as st
from openai import OpenAI

from pr_triage.domain.band import Band
from pr_triage.domain.labels import (
    BAND_LABELS,
    ESCALATION_LABELS,
    FIELD_LABELS,
    format_eur,
)
from pr_triage.domain.schemas import WorkflowResult
from pr_triage.domain.status import Reason, Status
from pr_triage.service import Outcome, iter_process_message
from pr_triage.workflow import Step, StepEvent

CSS_PATH = Path(__file__).parent / "style.css"

STEP_LABELS = {
    Step.SCREENING: "Verificar o texto",
    Step.EXTRACTION: "Extrair os dados do pedido",
    Step.VALIDATION: "Validar os dados",
    Step.BAND: "Determinar o escalão",
    Step.POLICY: "Consultar a política de compras",
    Step.DECISION: "Decisão",
    Step.SUMMARY: "Explicar o resultado",
}
STATE_ICONS = {"pending": "", "running": "", "done": "✓", "failed": "✕"}
EXAMPLES = [
    (
        "Cadeiras de escritório, 800 €",
        "Preciso de 5 cadeiras de escritório, 800 euros, centro de custo 1500",
    ),
    (
        "Cadeiras de escritório, 7 000 €",
        "Preciso de 3 cadeiras de escritório, 7000 euros, centro de custo 1500",
    ),
    (
        "Licenças de software, 2 400 €",
        "Preciso de 5 licenças de software de design, 2400 euros, centro de custo 1180",
    ),
]


@st.cache_resource
def get_client() -> OpenAI:
    return OpenAI()


def initial_states() -> dict:
    return {step: ("pending", "") for step in Step}


def reset() -> None:
    st.session_state.request_id = None
    st.session_state.result = None
    st.session_state.steps = None
    st.session_state.text = ""


def set_example(text: str) -> None:
    st.session_state.text = text


def render_stepper(states: dict) -> str:
    rows = []
    for step in Step:
        state, detail = states[step]
        detail_html = (
            f'<div class="step-detail">{html.escape(detail)}</div>' if detail else ""
        )
        rows.append(
            f'<div class="step"><div class="step-icon {state}">{STATE_ICONS[state]}</div>'
            f'<div><div class="step-label">{STEP_LABELS[step]}</div>{detail_html}</div></div>'
        )
    return '<div class="stepper">' + "".join(rows) + "</div>"


def banner(kind: str, icon: str, text: str) -> str:
    return (
        f'<div class="banner {kind}"><span>{icon}</span>'
        f"<span>{html.escape(text)}</span></div>"
    )


def format_value(value) -> str:
    if value is None or value == "":
        return "—"
    return html.escape(str(value))


def clause_body(text: str) -> str:
    if text.startswith("Documento:") and "\n" in text:
        return text.split("\n", 1)[1].strip()
    return text


def render_request(result: WorkflowResult) -> str:
    request = result.request
    rows = [
        ("Item", format_value(request.item)),
        ("Quantidade", format_value(request.quantity)),
        ("Valor estimado", format_eur(request.estimated_value_eur)),
        ("Centro de custo", format_value(request.cost_center)),
    ]
    items = "".join(f"<dt>{label}</dt><dd>{value}</dd>" for label, value in rows)
    return f'<dl class="kv">{items}</dl>'


def render_usage(result: WorkflowResult) -> None:
    if not result.calls:
        return
    count = len(result.calls)
    tokens = sum(c.input_tokens + c.output_tokens for c in result.calls)
    latency = sum(c.latency for c in result.calls)
    noun = "chamada" if count == 1 else "chamadas"
    st.markdown(
        f'<div class="muted">{count} {noun} · {tokens} tokens · {latency:.1f} s</div>',
        unsafe_allow_html=True,
    )


def render_result(result: WorkflowResult) -> None:
    if result.status == Status.REJECTED:
        if result.reason == Reason.SUSPICIOUS_ACTIVITY:
            text = "Pedido rejeitado: atividade suspeita"
        else:
            text = "Pedido rejeitado: dados inválidos — " + ", ".join(
                FIELD_LABELS[f] for f in result.invalid
            )
        st.markdown(banner("red", "✕", text), unsafe_allow_html=True)
        return

    if result.status == Status.NEEDS_INFO:
        text = "Faltam dados: " + ", ".join(FIELD_LABELS[f] for f in result.missing)
        st.markdown(banner("amber", "⚠", text), unsafe_allow_html=True)
        if result.follow_up:
            with st.container(border=True):
                st.markdown(
                    '<div class="card-title">Pergunta</div>', unsafe_allow_html=True
                )
                st.write(result.follow_up)
        else:
            st.markdown(
                '<div class="muted">Responde na caixa de texto com a informação em falta.</div>',
                unsafe_allow_html=True,
            )
        return

    if result.escalation:
        text = "Encaminhar para ação manual: " + ESCALATION_LABELS[result.escalation]
        st.markdown(banner("orange", "⚠", text), unsafe_allow_html=True)
    elif result.band == Band.NO_BLOCKERS:
        st.markdown(banner("green", "✓", BAND_LABELS[result.band]), unsafe_allow_html=True)
    else:
        st.markdown(banner("amber", "?", BAND_LABELS[result.band]), unsafe_allow_html=True)

    cited = set(result.summary.cited_chunk_ids) if result.summary else set()
    col_summary, col_request = st.columns([3, 2], gap="medium")

    with col_summary.container(border=True):
        st.markdown('<div class="card-title">Resumo</div>', unsafe_allow_html=True)
        if result.summary:
            st.write(result.summary.text)
            clauses = [e.clause for e in result.evidence if e.chunk_id in cited]
            st.markdown(
                f'<span class="chip">Cláusulas citadas: {" · ".join(clauses)}</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown('<div class="muted">Resumo indisponível.</div>', unsafe_allow_html=True)

    with col_request.container(border=True):
        st.markdown('<div class="card-title">Pedido</div>', unsafe_allow_html=True)
        st.markdown(render_request(result), unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown(
            '<div class="card-title">Evidência da política</div>', unsafe_allow_html=True
        )
        for evidence in result.evidence:
            score = f" · score {evidence.score:.2f}" if evidence.score is not None else ""
            mark = "📌 " if evidence.chunk_id in cited else ""
            with st.expander(f"{mark}{evidence.clause} · {evidence.title}{score}"):
                st.caption(f"{evidence.document} ({evidence.source})")
                st.write(clause_body(evidence.text))


st.set_page_config(page_title="Triagem de requisições de compra", layout="wide")
st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
st.session_state.setdefault("request_id", None)
st.session_state.setdefault("result", None)
st.session_state.setdefault("steps", None)
st.session_state.setdefault("text", "")

badge = (
    f'<span class="badge">Pedido #{st.session_state.request_id}</span>'
    if st.session_state.request_id is not None
    else ""
)
st.markdown(
    '<div class="topbar"><div class="topbar-icon">📋</div>'
    '<div class="topbar-title">Triagem de requisições de compra</div>'
    f"{badge}</div>",
    unsafe_allow_html=True,
)

left, right = st.columns([2, 3], gap="large")

with left:
    with st.container(border=True):
        st.markdown('<div class="card-title">Novo pedido</div>', unsafe_allow_html=True)
        st.text_area("Descreve o pedido de compra", key="text", height=160)
        col_submit, col_reset = st.columns(2)
        submit = col_submit.button(
            "Processar pedido", type="primary", use_container_width=True
        )
        col_reset.button("Novo pedido", on_click=reset, use_container_width=True)
        st.markdown('<div class="muted">EXEMPLOS</div>', unsafe_allow_html=True)
        for label, example in EXAMPLES:
            st.button(
                label,
                key=f"example-{label}",
                on_click=set_example,
                args=(example,),
                use_container_width=True,
            )

with right:
    steps_box = st.container(border=True)
    result_box = st.container()

with steps_box:
    st.markdown('<div class="card-title">Processamento</div>', unsafe_allow_html=True)
    steps_slot = st.empty()
    states = st.session_state.steps or initial_states()
    steps_slot.markdown(render_stepper(states), unsafe_allow_html=True)

if submit and st.session_state.text.strip():
    states = initial_states()
    steps_slot.markdown(render_stepper(states), unsafe_allow_html=True)
    outcome = None
    for event in iter_process_message(
        st.session_state.text, get_client(), st.session_state.request_id
    ):
        if isinstance(event, StepEvent):
            states[event.step] = (event.state, event.detail)
            steps_slot.markdown(render_stepper(states), unsafe_allow_html=True)
        elif isinstance(event, Outcome):
            outcome = event
    st.session_state.request_id = outcome.request_id
    st.session_state.result = outcome.result
    st.session_state.steps = states
    st.rerun()

if st.session_state.result is not None:
    with result_box:
        render_result(st.session_state.result)
        render_usage(st.session_state.result)
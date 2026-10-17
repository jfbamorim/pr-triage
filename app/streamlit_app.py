import streamlit as st
from openai import OpenAI

from pr_triage.domain.band import Band
from pr_triage.domain.schemas import WorkflowResult
from pr_triage.domain.status import EscalationReason, Reason, Status
from pr_triage.service import Outcome, iter_process_message
from pr_triage.workflow import Step, StepEvent

STEP_LABELS = {
    Step.SCREENING: "Verificar o texto",
    Step.EXTRACTION: "Extrair os dados do pedido",
    Step.VALIDATION: "Validar os dados",
    Step.BAND: "Determinar o escalão",
    Step.POLICY: "Consultar a política de compras",
    Step.DECISION: "Decisão",
    Step.SUMMARY: "Explicar o resultado",
}
STATE_ICONS = {"running": "⏳", "done": "✅", "failed": "❌"}
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


@st.cache_resource
def get_client() -> OpenAI:
    return OpenAI()


def reset() -> None:
    st.session_state.request_id = None
    st.session_state.result = None
    st.session_state.text = ""


def render_result(result: WorkflowResult) -> None:
    if result.status == Status.REJECTED:
        if result.reason == Reason.SUSPICIOUS_ACTIVITY:
            st.error("Pedido rejeitado: atividade suspeita.")
        else:
            st.error("Pedido rejeitado: dados inválidos — " + ", ".join(result.invalid))
        return

    if result.status == Status.NEEDS_INFO:
        st.warning("Faltam dados: " + ", ".join(result.missing))
        st.caption("Responde na caixa de texto com a informação em falta.")
        return

    if result.escalation:
        st.warning(
            "Encaminhar para ação manual: " + ESCALATION_LABELS[result.escalation]
        )
    else:
        st.success(BAND_LABELS[result.band])

    cited = set(result.summary.cited_chunk_ids) if result.summary else set()
    if result.summary:
        st.info(result.summary.text)
        clauses = [e.clause for e in result.evidence if e.chunk_id in cited]
        st.caption("Cláusulas citadas: " + ", ".join(clauses))
    else:
        st.caption("Resumo indisponível.")

    st.subheader("Pedido")
    st.json(result.request.model_dump())

    st.subheader("Evidência da política")
    for evidence in result.evidence:
        score = f" · score {evidence.score:.2f}" if evidence.score is not None else ""
        mark = "📌 " if evidence.chunk_id in cited else ""
        with st.expander(f"{mark}{evidence.clause} · {evidence.title}{score}"):
            st.caption(f"{evidence.document} ({evidence.source})")
            st.write(evidence.text)


st.set_page_config(page_title="Triagem de requisições de compra")
st.session_state.setdefault("request_id", None)
st.session_state.setdefault("result", None)

st.title("Triagem de requisições de compra")

st.text_area("Descreve o pedido de compra", key="text", height=120)
col_submit, col_reset = st.columns([1, 1])
submit = col_submit.button("Processar pedido", type="primary")
col_reset.button("Novo pedido", on_click=reset)

if st.session_state.request_id is not None:
    st.caption(f"Pedido #{st.session_state.request_id}")

if submit and st.session_state.text.strip():
    placeholders = {}
    outcome = None
    with st.status("A processar o pedido...", expanded=True) as status:
        for step in Step:
            placeholders[step] = st.empty()
            placeholders[step].write(f"⚪ {STEP_LABELS[step]}")
        for event in iter_process_message(
            st.session_state.text, get_client(), st.session_state.request_id
        ):
            if isinstance(event, StepEvent):
                detail = f" — {event.detail}" if event.detail else ""
                placeholders[event.step].write(
                    f"{STATE_ICONS[event.state]} {STEP_LABELS[event.step]}{detail}"
                )
            elif isinstance(event, Outcome):
                outcome = event
        status.update(label="Pedido processado", state="complete", expanded=True)
    st.session_state.request_id = outcome.request_id
    st.session_state.result = outcome.result

if st.session_state.result is not None:
    render_result(st.session_state.result)
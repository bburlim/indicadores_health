import streamlit as st
from datadog_client import get_monitors

st.set_page_config(page_title="Monitors | Health Dashboard", layout="wide")
st.title("Monitors")
st.caption("Status de todos os alertas configurados no Datadog (env: prod)")

STATE_ICON = {
    "OK": "OK",
    "Alert": "ALERTA",
    "Warn": "AVISO",
    "No Data": "SEM DADOS",
}

with st.spinner("Carregando monitors..."):
    try:
        monitors = get_monitors()
    except Exception as e:
        st.error(f"Erro ao buscar monitors: {e}")
        st.stop()

states_options = ["Todos", "Alert", "Warn", "OK", "No Data"]
selected_state = st.selectbox("Filtrar por estado", states_options)

filtered = monitors
if selected_state != "Todos":
    filtered = [m for m in monitors if m.get("overall_state") == selected_state]

st.write(f"Exibindo **{len(filtered)}** monitor(s)")
st.divider()

for m in filtered:
    state = m.get("overall_state", "No Data")
    icon = STATE_ICON.get(state, state)
    name = m.get("name", "Sem nome")
    modified = (m.get("overall_state_modified") or "")[:10]
    mtype = m.get("type", "")
    thresholds = m.get("options", {}).get("thresholds", {})
    query = m.get("query", "")
    msg = m.get("message", "")

    expanded = state in ("Alert", "Warn")
    with st.expander(f"[{icon}] {name}", expanded=expanded):
        col1, col2 = st.columns(2)
        col1.write(f"**Tipo:** `{mtype}`")
        col1.write(f"**Estado modificado em:** {modified}")
        if thresholds:
            col2.write(f"**Critico:** {thresholds.get('critical', 'N/A')}")
            col2.write(f"**Aviso:** {thresholds.get('warning', 'N/A')}")
        if query:
            st.code(query, language="text")
        if msg:
            st.caption(msg[:400])

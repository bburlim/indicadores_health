import streamlit as st
import pandas as pd
from datadog_client import get_error_logs, get_log_error_counts

st.set_page_config(page_title="Logs de Erro | Health Dashboard", layout="wide")
st.title("Logs de Erro")
st.caption("Logs com status ERROR em producao (env: prod)")

window_options = {
    "Ultima 15 minutos": "now-15m",
    "Ultima 1 hora": "now-1h",
    "Ultimas 3 horas": "now-3h",
    "Ultimas 6 horas": "now-6h",
}
selected_window_label = st.selectbox("Janela de tempo", list(window_options.keys()), index=1)
selected_window = window_options[selected_window_label]

limit = st.slider("Quantidade de logs", min_value=10, max_value=200, value=50, step=10)

with st.spinner("Carregando logs de erro..."):
    try:
        logs = get_error_logs(limit=limit, window=selected_window)
        error_counts = get_log_error_counts(window=selected_window)
    except Exception as e:
        st.error(f"Erro ao buscar logs: {e}")
        st.stop()

# Summary
col1, col2 = st.columns([1, 2])
with col1:
    st.metric("Erros encontrados", len(logs))

with col2:
    if error_counts:
        df_counts = pd.DataFrame(
            list(error_counts.items()), columns=["Servico", "Erros"]
        ).sort_values("Erros", ascending=False)
        st.dataframe(df_counts, use_container_width=True, hide_index=True)

st.divider()

# Log table
st.subheader("Detalhes dos erros")

if not logs:
    st.success("Nenhum erro encontrado na janela selecionada.")
else:
    service_filter = st.multiselect(
        "Filtrar por servico",
        options=sorted(set(e.get("attributes", {}).get("service", "unknown") for e in logs)),
    )

    rows = []
    for entry in logs:
        attrs = entry.get("attributes", {})
        inner = attrs.get("attributes", {})
        svc = attrs.get("service", "unknown")

        if service_filter and svc not in service_filter:
            continue

        timestamp = attrs.get("timestamp", "")[:19].replace("T", " ")
        message = attrs.get("message", "")
        logger = inner.get("logger_name", "")
        if logger:
            logger = logger.split(".")[-1]
        tenant = inner.get("tennant_uuid", "")
        stack = inner.get("stack_trace", "")
        first_line = stack.split("\n")[0] if stack else ""

        rows.append({
            "Timestamp": timestamp,
            "Servico": svc,
            "Logger": logger,
            "Mensagem": message,
            "Causa": first_line[:120],
            "Tenant": tenant,
        })

    if rows:
        df_logs = pd.DataFrame(rows)
        st.dataframe(df_logs, use_container_width=True, hide_index=True)

        # Expandable detail view
        st.subheader("Stack trace completo")
        for i, entry in enumerate(logs):
            attrs = entry.get("attributes", {})
            inner = attrs.get("attributes", {})
            svc = attrs.get("service", "unknown")

            if service_filter and svc not in service_filter:
                continue

            stack = inner.get("stack_trace", "")
            if not stack:
                continue

            timestamp = attrs.get("timestamp", "")[:19].replace("T", " ")
            msg = attrs.get("message", "")
            logger = inner.get("logger_name", "").split(".")[-1]

            with st.expander(f"[{timestamp}] {svc} | {logger}: {msg[:80]}"):
                st.code(stack, language="text")
    else:
        st.info("Nenhum log encontrado com os filtros selecionados.")

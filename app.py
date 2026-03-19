import time
import streamlit as st
import pandas as pd
from datadog_client import (
    get_monitors,
    get_service_metrics,
    get_queue_metrics,
    get_log_error_counts,
    get_kubernetes_containers,
)

st.set_page_config(
    page_title="EmiteAI | Health Dashboard",
    page_icon="",
    layout="wide",
)

REFRESH_INTERVAL_S = 300  # 5 minutes

# ---- Auto-refresh ----
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

elapsed = time.time() - st.session_state.last_refresh
if elapsed >= REFRESH_INTERVAL_S:
    st.cache_data.clear()
    st.session_state.last_refresh = time.time()
    st.rerun()

# ---- Header ----
col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("EmiteAI | Health Dashboard")
with col_status:
    last_update = time.strftime("%H:%M:%S", time.localtime(st.session_state.last_refresh))
    next_refresh = int(REFRESH_INTERVAL_S - elapsed)
    st.caption(f"Atualizado em: {last_update}")
    st.caption(f"Proxima atualizacao em: {next_refresh}s")
    if st.button("Atualizar agora"):
        st.cache_data.clear()
        st.session_state.last_refresh = time.time()
        st.rerun()

st.divider()

# ---- Load data ----
with st.spinner("Carregando dados..."):
    try:
        monitors = get_monitors()
        svc = get_service_metrics()
        queues = get_queue_metrics()
        error_counts = get_log_error_counts()
        containers = get_kubernetes_containers()
    except Exception as e:
        st.error(f"Erro ao carregar dados do Datadog: {e}")
        st.stop()

# ---- Monitor status summary ----
st.subheader("Status dos Monitors")

monitor_states = {"OK": 0, "Alert": 0, "Warn": 0, "No Data": 0}
for m in monitors:
    state = m.get("overall_state", "No Data")
    if state in monitor_states:
        monitor_states[state] += 1
    else:
        monitor_states["No Data"] += 1

col1, col2, col3, col4 = st.columns(4)
col1.metric("OK", monitor_states["OK"], delta=None)
col2.metric("Alerta", monitor_states["Alert"], delta=None)
col3.metric("Aviso", monitor_states["Warn"], delta=None)
col4.metric("Sem dados", monitor_states["No Data"], delta=None)

any_alert = monitor_states["Alert"] > 0
any_warn = monitor_states["Warn"] > 0
if any_alert:
    st.error("Existe(m) monitor(s) em estado de ALERTA.")
elif any_warn:
    st.warning("Existe(m) monitor(s) em estado de AVISO.")
else:
    st.success("Todos os monitors estao OK.")

st.divider()

# ---- Key metrics ----
st.subheader("Metricas Principais (ultima 1h)")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric(
    "Requisicoes HTTP",
    f"{svc['total_hits']:,}",
)
c2.metric(
    "Erros HTTP",
    f"{svc['total_errors']:,}",
    delta=f"{svc['error_rate_pct']}% error rate",
    delta_color="inverse",
)
c3.metric(
    "Latencia media",
    f"{svc['avg_latency_ms']} ms" if svc["avg_latency_ms"] else "N/A",
)
c4.metric(
    "Mensagens nas filas",
    f"{queues['total_messages']:,}",
)
c5.metric(
    "Containers rodando",
    containers if containers else "N/A",
)

st.divider()

# ---- Errors by service ----
st.subheader("Erros por Servico (ultima 1h)")

if error_counts:
    df_errors = pd.DataFrame(
        list(error_counts.items()), columns=["Servico", "Erros"]
    ).sort_values("Erros", ascending=False)
    st.bar_chart(df_errors.set_index("Servico"), color="#FF4B4B")
else:
    st.info("Nenhum erro encontrado na ultima hora.")

st.divider()

# ---- Queue latency top 10 ----
st.subheader("Latencia das Filas (top 10)")

if queues.get("queue_latency"):
    ql = queues["queue_latency"]
    df_ql = (
        pd.DataFrame(list(ql.items()), columns=["Fila", "Latencia (ms)"])
        .sort_values("Latencia (ms)", ascending=False)
        .head(10)
    )
    st.dataframe(df_ql, use_container_width=True, hide_index=True)
else:
    st.info("Dados de latencia de filas nao disponiveis.")

st.caption("Use o menu lateral para ver detalhes por secao.")

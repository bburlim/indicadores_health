import streamlit as st
import pandas as pd
from datetime import datetime
from datadog_client import get_queue_metrics, get_monitors

st.set_page_config(page_title="Filas | Health Dashboard", layout="wide")
st.title("Filas (RabbitMQ / AMQP)")
st.caption("Throughput e latencia das filas de mensagens (env: prod, ultima 1h)")

with st.spinner("Carregando metricas de filas..."):
    try:
        queues = get_queue_metrics()
        monitors = get_monitors()
    except Exception as e:
        st.error(f"Erro ao buscar metricas: {e}")
        st.stop()

# Shopee queue monitor status
shopee_monitor = next(
    (m for m in monitors if "shopee" in m.get("name", "").lower() and "fila" in m.get("name", "").lower()),
    None,
)
if shopee_monitor:
    state = shopee_monitor.get("overall_state", "No Data")
    thresholds = shopee_monitor.get("options", {}).get("thresholds", {})
    if state == "OK":
        st.success(f"Monitor 'Fila da Shopee': OK | Critico: {thresholds.get('critical')} ms | Aviso: {thresholds.get('warning')} ms")
    elif state == "Alert":
        st.error(f"Monitor 'Fila da Shopee': ALERTA | Critico: {thresholds.get('critical')} ms")
    else:
        st.warning(f"Monitor 'Fila da Shopee': {state}")

st.divider()

# KPI
st.metric("Total de mensagens processadas (1h)", f"{queues['total_messages']:,}")

st.divider()

# Timeseries throughput
st.subheader("Throughput de mensagens (5min)")
if queues["hits_timeseries"]:
    rows = []
    for s in queues["hits_timeseries"]:
        for ts, val in zip(s["timestamps"], s["values"]):
            rows.append({"Horario": datetime.fromtimestamp(ts), "Mensagens": val})
    df = pd.DataFrame(rows)
    st.line_chart(df.set_index("Horario")["Mensagens"])
else:
    st.info("Dados de timeseries nao disponiveis.")

st.divider()

# Latency table
st.subheader("Latencia media por fila (ms)")
if queues.get("queue_latency"):
    df_lat = (
        pd.DataFrame(
            list(queues["queue_latency"].items()),
            columns=["Fila", "Latencia media (ms)"],
        )
        .sort_values("Latencia media (ms)", ascending=False)
    )

    def highlight_latency(val):
        if val > 2000:
            return "background-color: #FF4B4B; color: white"
        elif val > 1500:
            return "background-color: #FFA500; color: white"
        return ""

    styled = df_lat.style.applymap(highlight_latency, subset=["Latencia media (ms)"])
    st.dataframe(styled, use_container_width=True, hide_index=True)
    st.caption("Vermelho: acima de 2000ms (critico) | Laranja: acima de 1500ms (aviso)")
else:
    st.info("Dados de latencia por fila nao disponiveis.")

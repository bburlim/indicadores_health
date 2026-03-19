import streamlit as st
import pandas as pd
from datetime import datetime
from datadog_client import get_service_metrics

st.set_page_config(page_title="Servicos | Health Dashboard", layout="wide")
st.title("APIs e Servicos")
st.caption("Metricas de requisicoes HTTP/Spring (env: prod, ultima 1h)")

with st.spinner("Carregando metricas de servicos..."):
    try:
        svc = get_service_metrics()
    except Exception as e:
        st.error(f"Erro ao buscar metricas: {e}")
        st.stop()

# KPIs
c1, c2, c3 = st.columns(3)
c1.metric("Requisicoes (1h)", f"{svc['total_hits']:,}")
c2.metric(
    "Erros (1h)",
    f"{svc['total_errors']:,}",
    delta=f"{svc['error_rate_pct']}% error rate",
    delta_color="inverse",
)
c3.metric(
    "Latencia media",
    f"{svc['avg_latency_ms']} ms" if svc["avg_latency_ms"] else "N/A",
)

st.divider()

# Error rate gauge
error_rate = svc["error_rate_pct"]
if error_rate < 1:
    st.success(f"Error rate: {error_rate}% — dentro do esperado")
elif error_rate < 5:
    st.warning(f"Error rate: {error_rate}% — atencao necessaria")
else:
    st.error(f"Error rate: {error_rate}% — nivel critico")

st.divider()

# Timeseries charts
def build_df(series_list, value_label):
    rows = []
    for s in series_list:
        for ts, val in zip(s["timestamps"], s["values"]):
            rows.append({
                "Horario": datetime.fromtimestamp(ts),
                value_label: val,
                "Escopo": s["scope"],
            })
    return pd.DataFrame(rows)


st.subheader("Requisicoes por intervalo (5min)")
if svc["hits_timeseries"]:
    df_hits = build_df(svc["hits_timeseries"], "Requisicoes")
    st.line_chart(df_hits.set_index("Horario")["Requisicoes"])
else:
    st.info("Dados de timeseries nao disponiveis.")

st.subheader("Erros por intervalo (5min)")
if svc["errors_timeseries"]:
    df_err = build_df(svc["errors_timeseries"], "Erros")
    st.line_chart(df_err.set_index("Horario")["Erros"], color="#FF4B4B")
else:
    st.info("Dados de timeseries de erros nao disponiveis.")

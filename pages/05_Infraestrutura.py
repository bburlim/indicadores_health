import streamlit as st
import pandas as pd
from datadog_client import get_kubernetes_containers, get_container_restarts

st.set_page_config(page_title="Infraestrutura | Health Dashboard", layout="wide")
st.title("Infraestrutura")
st.caption("Kubernetes (AKS Production) — pods, containers e restarts")

with st.spinner("Carregando dados de infraestrutura..."):
    try:
        containers = get_kubernetes_containers()
        restarts = get_container_restarts()
    except Exception as e:
        st.error(f"Erro ao buscar dados: {e}")
        st.stop()

col1, col2 = st.columns(2)
col1.metric(
    "Containers rodando (prod)",
    containers if containers is not None else "N/A",
)
col2.metric(
    "Deployments com restarts (1h)",
    len(restarts),
    delta=len(restarts) if restarts else None,
    delta_color="inverse",
)

st.divider()

st.subheader("Restarts de containers por deployment (ultima 1h)")

if restarts:
    df_restarts = (
        pd.DataFrame(
            list(restarts.items()), columns=["Deployment", "Restarts"]
        )
        .sort_values("Restarts", ascending=False)
    )

    def highlight_restarts(val):
        if val >= 5:
            return "background-color: #FF4B4B; color: white"
        elif val >= 2:
            return "background-color: #FFA500; color: white"
        return ""

    styled = df_restarts.style.applymap(highlight_restarts, subset=["Restarts"])
    st.dataframe(styled, use_container_width=True, hide_index=True)
    st.caption("Vermelho: 5+ restarts | Laranja: 2+ restarts")
else:
    st.success("Nenhum restart de container na ultima hora.")

st.divider()
st.subheader("Referencia de deployments conhecidos")

deployments_info = {
    "api-helm": "API principal",
    "app-helm": "App NFS-e processamento",
    "nfse-api-helm": "API NFS-e",
    "shp-app-apartada-default-helm": "Shopee App (isolado)",
    "shp-shopee-app-apartada-default-helm": "Shopee App principal",
}

df_deploy = pd.DataFrame(
    list(deployments_info.items()), columns=["Deployment", "Descricao"]
)
st.dataframe(df_deploy, use_container_width=True, hide_index=True)

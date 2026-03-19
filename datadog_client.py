import time
import requests
import streamlit as st


def _get_credentials():
    try:
        api_key = st.secrets["DD_API_KEY"]
        app_key = st.secrets["DD_APP_KEY"]
        site = st.secrets.get("DD_SITE", "datadoghq.com")
    except Exception:
        import os
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.environ["DD_API_KEY"]
        app_key = os.environ["DD_APP_KEY"]
        site = os.environ.get("DD_SITE", "datadoghq.com")
    return api_key, app_key, site


def _headers():
    api_key, app_key, _ = _get_credentials()
    return {
        "DD-API-KEY": api_key,
        "DD-APPLICATION-KEY": app_key,
        "Content-Type": "application/json",
    }


def _base(site=None):
    _, _, s = _get_credentials()
    return f"https://api.{site or s}"


@st.cache_data(ttl=300)
def get_monitors():
    url = f"{_base()}/api/v1/monitor"
    resp = requests.get(url, headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=300)
def query_metric(query: str, window_seconds: int = 3600):
    now = int(time.time())
    frm = now - window_seconds
    url = f"{_base()}/api/v1/query"
    resp = requests.get(
        url,
        headers=_headers(),
        params={"from": frm, "to": now, "query": query},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=300)
def get_error_logs(limit: int = 50, window: str = "now-1h"):
    url = f"{_base()}/api/v2/logs/events/search"
    payload = {
        "filter": {
            "from": window,
            "to": "now",
            "query": "env:prod status:error",
        },
        "sort": "-timestamp",
        "page": {"limit": limit},
    }
    resp = requests.post(url, headers=_headers(), json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json().get("data", [])


@st.cache_data(ttl=300)
def get_log_error_counts(window: str = "now-1h"):
    """Returns error count grouped by service via pagination (log search)."""
    url = f"{_base()}/api/v2/logs/events/search"
    payload = {
        "filter": {"from": window, "to": "now", "query": "env:prod status:error"},
        "sort": "-timestamp",
        "page": {"limit": 1000},
    }
    resp = requests.post(url, headers=_headers(), json=payload, timeout=15)
    resp.raise_for_status()
    from collections import Counter
    data = resp.json().get("data", [])
    svc_count = Counter()
    for e in data:
        svc = e.get("attributes", {}).get("service", "unknown")
        svc_count[svc] += 1
    return dict(svc_count.most_common())


@st.cache_data(ttl=300)
def get_kubernetes_containers():
    now = int(time.time())
    frm = now - 300
    url = f"{_base()}/api/v1/query"
    resp = requests.get(
        url,
        headers=_headers(),
        params={
            "from": frm,
            "to": now,
            "query": "sum:kubernetes.containers.running{cluster_name:aks-production}",
        },
        timeout=15,
    )
    resp.raise_for_status()
    series = resp.json().get("series", [])
    if not series:
        return None
    pts = [v[1] for v in series[0].get("pointlist", []) if v[1] is not None]
    return int(pts[-1]) if pts else None


@st.cache_data(ttl=300)
def get_container_restarts():
    now = int(time.time())
    frm = now - 3600
    url = f"{_base()}/api/v1/query"
    resp = requests.get(
        url,
        headers=_headers(),
        params={
            "from": frm,
            "to": now,
            "query": "sum:kubernetes.containers.restarts{cluster_name:aks-production}.by{kube_deployment}",
        },
        timeout=15,
    )
    resp.raise_for_status()
    result = {}
    for s in resp.json().get("series", []):
        scope = s.get("scope", "")
        deployment = scope.replace("kube_deployment:", "")
        pts = [v[1] for v in s.get("pointlist", []) if v[1] is not None]
        total = int(sum(pts)) if pts else 0
        if total > 0:
            result[deployment] = total
    return result


def _extract_series_total(series_list):
    result = {}
    for s in series_list:
        scope = s.get("scope", "all")
        pts = [v[1] for v in s.get("pointlist", []) if v[1] is not None]
        result[scope] = int(sum(pts)) if pts else 0
    return result


def _extract_series_avg_ms(series_list):
    result = {}
    for s in series_list:
        scope = s.get("scope", "all")
        pts = [v[1] for v in s.get("pointlist", []) if v[1] is not None]
        avg_ns = sum(pts) / len(pts) if pts else 0
        result[scope] = round(avg_ns / 1e6, 1)
    return result


def _extract_timeseries(series_list):
    """Returns list of {scope, timestamps, values} for chart rendering."""
    result = []
    for s in series_list:
        pts = [(v[0] / 1000, v[1]) for v in s.get("pointlist", []) if v[1] is not None]
        if pts:
            result.append({
                "scope": s.get("scope", "all"),
                "timestamps": [p[0] for p in pts],
                "values": [p[1] for p in pts],
            })
    return result


@st.cache_data(ttl=300)
def get_service_metrics():
    now = int(time.time())
    frm = now - 3600

    def q(query):
        resp = requests.get(
            f"{_base()}/api/v1/query",
            headers=_headers(),
            params={"from": frm, "to": now, "query": query},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("series", [])

    hits_series = q("sum:trace.spring.handler.hits{env:prod}.as_count().rollup(sum,300)")
    errors_series = q("sum:trace.spring.handler.errors{env:prod}.as_count().rollup(sum,300)")
    latency_series = q("avg:trace.spring.handler{env:prod}.rollup(avg,300)")

    total_hits = sum(_extract_series_total(hits_series).values())
    total_errors = sum(_extract_series_total(errors_series).values())
    avg_latency_ms = None
    for s in latency_series:
        pts = [v[1] for v in s.get("pointlist", []) if v[1] is not None]
        if pts:
            avg_latency_ms = round(sum(pts) / len(pts) / 1e6, 1)
            break

    error_rate = round((total_errors / total_hits * 100), 2) if total_hits > 0 else 0.0

    return {
        "total_hits": total_hits,
        "total_errors": total_errors,
        "error_rate_pct": error_rate,
        "avg_latency_ms": avg_latency_ms,
        "hits_timeseries": _extract_timeseries(hits_series),
        "errors_timeseries": _extract_timeseries(errors_series),
    }


@st.cache_data(ttl=300)
def get_queue_metrics():
    now = int(time.time())
    frm = now - 3600

    def q(query):
        resp = requests.get(
            f"{_base()}/api/v1/query",
            headers=_headers(),
            params={"from": frm, "to": now, "query": query},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("series", [])

    hits_series = q("sum:trace.amqp.command.hits{env:prod}.as_count().rollup(sum,300)")
    duration_series = q(
        "sum:trace.amqp.command.duration{env:prod}.rollup(avg,300)"
        ".by{resource_name}"
    )

    total_messages = sum(_extract_series_total(hits_series).values())

    queue_latency = {}
    for s in duration_series:
        resource = s.get("scope", "").replace("resource_name:", "").split(",")[0]
        pts = [v[1] for v in s.get("pointlist", []) if v[1] is not None]
        if pts:
            avg_ms = round(sum(pts) / len(pts) / 1e6, 1)
            queue_latency[resource] = avg_ms

    return {
        "total_messages": total_messages,
        "hits_timeseries": _extract_timeseries(hits_series),
        "queue_latency": queue_latency,
    }

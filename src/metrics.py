from prometheus_client import Counter, Gauge, Histogram

REQUESTS = Counter(
    "http_requests_total",
    "Requetes HTTP recues",
    ["endpoint", "code"],
)

LATENCY = Histogram(
    "http_request_duration_seconds",
    "Duree de traitement des requetes HTTP",
    ["endpoint"],
)

BUILD_INFO = Gauge(
    "app_build_info",
    "Version et commit en cours d'execution",
    ["version", "commit"],
)

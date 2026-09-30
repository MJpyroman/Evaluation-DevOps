import redis
from prometheus_client import REGISTRY

import app as app_module


def sample(name, **labels):
    return REGISTRY.get_sample_value(name, labels) or 0.0


class BrokenRedis:
    def incr(self, key):
        raise redis.ConnectionError("Redis injoignable")


def test_requests_are_counted_by_endpoint_and_code(client):
    before = sample("http_requests_total", endpoint="/", code="200")
    client.get("/")
    client.get("/")
    assert sample("http_requests_total", endpoint="/", code="200") == before + 2


def test_server_errors_are_counted_as_5xx(monkeypatch, client):
    monkeypatch.setattr(app_module, "get_redis", lambda: BrokenRedis())
    before = sample("http_requests_total", endpoint="/visits", code="500")
    assert client.get("/visits").status_code == 500
    assert sample("http_requests_total", endpoint="/visits", code="500") == before + 1


def test_unknown_urls_share_a_single_series(client):
    before = sample("http_requests_total", endpoint="unmatched", code="404")
    client.get("/inconnue-1")
    client.get("/inconnue-2")
    assert sample("http_requests_total", endpoint="unmatched", code="404") == before + 2


def test_latency_is_observed_per_route(client):
    before = sample("http_request_duration_seconds_count", endpoint="/")
    client.get("/")
    assert sample("http_request_duration_seconds_count", endpoint="/") == before + 1
    assert sample("http_request_duration_seconds_bucket", endpoint="/", le="+Inf") >= 1


def test_scrapes_of_metrics_are_not_counted(client):
    client.get("/metrics")
    response = client.get("/metrics")
    assert response.content_type.startswith("text/plain")
    assert 'endpoint="/metrics"' not in response.get_data(as_text=True)


def test_build_info_exposes_version_and_commit(client):
    body = client.get("/metrics").get_data(as_text=True)
    assert "# TYPE app_build_info gauge" in body
    labels = {"version": app_module.APP_VERSION, "commit": app_module.APP_COMMIT}
    assert sample("app_build_info", **labels) == 1
    assert client.get("/").get_json()["commit"] == app_module.APP_COMMIT

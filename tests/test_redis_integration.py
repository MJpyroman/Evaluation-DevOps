import os

import pytest
import redis

import app as app_module


@pytest.fixture
def real_redis():
    client = app_module.get_redis()
    try:
        client.ping()
    except redis.RedisError as exc:
        if os.getenv("CI"):
            pytest.fail(f"Redis injoignable en CI : {exc}")
        pytest.skip("aucun Redis joignable (REDIS_HOST / REDIS_PORT)")
    client.delete("visits")
    yield client
    client.delete("visits")


def test_visits_are_persisted_in_redis(client, real_redis):
    assert client.get("/visits").get_json() == {"visits": 1}
    assert client.get("/visits").get_json() == {"visits": 2}
    assert real_redis.get("visits") == "2"


def test_health_is_ok_against_real_redis(client, real_redis):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["redis"] == "up"

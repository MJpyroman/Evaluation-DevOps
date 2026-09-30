import redis

import app as app_module


class FakeRedis:
    def __init__(self, up=True):
        self.up = up
        self.counter = 0

    def ping(self):
        if not self.up:
            raise redis.ConnectionError("Redis injoignable")
        return True

    def incr(self, key):
        self.counter += 1
        return self.counter


def use_redis(monkeypatch, fake):
    monkeypatch.setattr(app_module, "get_redis", lambda: fake)


def test_index_names_the_service(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.get_json()["service"] == "evaluation-devops"


def test_health_is_ok_when_redis_answers(monkeypatch, client):
    use_redis(monkeypatch, FakeRedis(up=True))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "redis": "up"}


def test_health_is_503_when_redis_is_down(monkeypatch, client):
    use_redis(monkeypatch, FakeRedis(up=False))
    response = client.get("/health")
    assert response.status_code == 503
    assert response.get_json()["redis"] == "down"


def test_visits_increments_the_counter(monkeypatch, client):
    use_redis(monkeypatch, FakeRedis())
    assert client.get("/visits").get_json() == {"visits": 1}
    assert client.get("/visits").get_json() == {"visits": 2}

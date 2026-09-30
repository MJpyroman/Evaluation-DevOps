import os
import time
from functools import lru_cache

import redis
from flask import Flask, Response, g, jsonify, request
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from metrics import BUILD_INFO, LATENCY, REQUESTS

SERVICE_NAME = "evaluation-devops"
APP_VERSION = os.getenv("APP_VERSION", "dev")
APP_COMMIT = os.getenv("APP_COMMIT", "unknown")

app = Flask(__name__)
BUILD_INFO.labels(version=APP_VERSION, commit=APP_COMMIT).set(1)


@lru_cache(maxsize=1)
def get_redis():
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        socket_connect_timeout=2,
        socket_timeout=2,
        decode_responses=True,
    )


@app.before_request
def start_timer():
    g.started = time.perf_counter()


@app.after_request
def record_metrics(response):
    if request.path == "/metrics":
        return response
    endpoint = request.url_rule.rule if request.url_rule else "unmatched"
    REQUESTS.labels(endpoint=endpoint, code=str(response.status_code)).inc()
    LATENCY.labels(endpoint=endpoint).observe(time.perf_counter() - g.started)
    return response


@app.get("/")
def index():
    return jsonify(service=SERVICE_NAME, version=APP_VERSION, commit=APP_COMMIT)


@app.get("/health")
def health():
    try:
        get_redis().ping()
    except redis.RedisError as exc:
        app.logger.warning("healthcheck KO : %s", exc)
        return jsonify(status="error", redis="down"), 503
    return jsonify(status="ok", redis="up")


@app.get("/visits")
def visits():
    return jsonify(visits=get_redis().incr("visits"))


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), content_type=CONTENT_TYPE_LATEST)

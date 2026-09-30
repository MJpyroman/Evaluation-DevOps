import os
from functools import lru_cache

import redis
from flask import Flask, jsonify

SERVICE_NAME = "evaluation-devops"

app = Flask(__name__)


@lru_cache(maxsize=1)
def get_redis():
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        socket_connect_timeout=2,
        socket_timeout=2,
        decode_responses=True,
    )


@app.get("/")
def index():
    return jsonify(service=SERVICE_NAME)


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

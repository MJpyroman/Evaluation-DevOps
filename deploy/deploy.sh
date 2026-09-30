#!/usr/bin/env bash
set -euo pipefail

IMAGE="${1:?usage : deploy.sh IMAGE}"
HEALTH_URL="${HEALTH_URL:-http://localhost:8080/health}"

cd "$(dirname "$0")/.."

log() { printf '[deploy] %s\n' "$*"; }

running_image() {
    local id
    id="$(docker compose ps --quiet app)"
    if [ -n "$id" ]; then
        docker inspect --format '{{.Config.Image}}' "$id"
    fi
}

start() {
    APP_IMAGE="$1" docker compose up --detach --no-build
}

healthy() {
    curl --fail --no-progress-meter --max-time 5 \
        --retry 3 --retry-delay 5 --retry-all-errors "$HEALTH_URL" && echo
}

previous="$(running_image)"
log "en service : ${previous:-aucune version}"
log "a deployer : $IMAGE"

APP_IMAGE="$IMAGE" docker compose pull --quiet app
start "$IMAGE"

if healthy; then
    log "OK : $IMAGE repond sur $HEALTH_URL"
    exit 0
fi

log "ECHEC : $IMAGE ne repond pas sur $HEALTH_URL"
if [ -n "$previous" ] && [ "$previous" != "$IMAGE" ]; then
    log "rollback : re-pull de $previous"
    APP_IMAGE="$previous" docker compose pull --quiet app \
        || log "pull impossible, image locale reutilisee"
    start "$previous"
    if healthy; then
        log "rollback OK : $previous est de nouveau en service"
    else
        log "rollback KO : intervention manuelle necessaire"
    fi
fi
exit 1

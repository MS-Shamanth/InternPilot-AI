#!/bin/sh
# Container start-up (design.md §18, R11.4): migrate -> seed -> serve.
# Any failing step stops the container with a non-zero exit code.
set -eu

log() {
    echo "docker-entrypoint: $*" >&2
}

MIGRATE_MAX_ATTEMPTS="${MIGRATE_MAX_ATTEMPTS:-10}"
MIGRATE_RETRY_SECONDS="${MIGRATE_RETRY_SECONDS:-3}"

# Compose waits for the db healthcheck, but Postgres can still refuse connections briefly
# (or the backend may run against an external database), so retry a bounded number of times.
attempt=1
until alembic upgrade head; do
    if [ "$attempt" -ge "$MIGRATE_MAX_ATTEMPTS" ]; then
        log "alembic upgrade head failed after ${attempt} attempts; giving up"
        exit 1
    fi
    log "alembic upgrade head failed (attempt ${attempt}/${MIGRATE_MAX_ATTEMPTS}); retrying in ${MIGRATE_RETRY_SECONDS}s"
    attempt=$((attempt + 1))
    sleep "$MIGRATE_RETRY_SECONDS"
done
log "migrations applied"

if ! python -m app.cli seed; then
    log "seed failed; see the error above"
    exit 1
fi
log "seed complete"

log "starting API on 0.0.0.0:8000"
exec uvicorn --factory app.asgi:build_app --host 0.0.0.0 --port 8000

#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/finances-app}"
BRANCH="${BRANCH:-master}"
LOCK_FILE="/run/lock/finances-app-deploy.lock"

exec 9>"$LOCK_FILE"
flock -n 9 || exit 0

cd "$APP_DIR"

if [[ ! -d .git ]]; then
  echo "Deploy interrompido: $APP_DIR não é um clone Git." >&2
  exit 1
fi

git fetch --prune origin "$BRANCH"

LOCAL_SHA="$(git rev-parse HEAD)"
REMOTE_SHA="$(git rev-parse "origin/$BRANCH")"

if [[ "$LOCAL_SHA" == "$REMOTE_SHA" ]]; then
  echo "[$(date --iso-8601=seconds)] Sem atualizações ($LOCAL_SHA)."
  exit 0
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Deploy interrompido: existem alterações locais no checkout." >&2
  git status --short >&2
  exit 1
fi

git pull --ff-only origin "$BRANCH"
docker compose config --quiet
docker compose up -d --build --remove-orphans

for attempt in {1..30}; do
  if curl --fail --silent --show-error --max-time 3 http://127.0.0.1:8000/health >/dev/null; then
    echo "[$(date --iso-8601=seconds)] Deploy concluído: $LOCAL_SHA -> $REMOTE_SHA"
    exit 0
  fi
  sleep 2
done

echo "Deploy aplicado, mas o health check não respondeu a tempo." >&2
docker compose ps >&2
exit 1

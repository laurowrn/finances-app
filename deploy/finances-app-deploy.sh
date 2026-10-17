#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/finances-app}"
BRANCH="${BRANCH:-master}"
LOCK_FILE="/run/lock/finances-app-deploy.lock"
STATE_DIR="${STATE_DIR:-/var/lib/finances-app}"
STATUS_FILE="$STATE_DIR/deploy-status.json"

mkdir -p "$STATE_DIR"

write_status() {
  local state="$1"
  local commit="${2:-}"
  local timestamp
  timestamp="$(date --iso-8601=seconds)"
  printf '{"status":"%s","commit":"%s","updated_at":"%s"}\n' \
    "$state" "$commit" "$timestamp" > "$STATUS_FILE.tmp"
  mv "$STATUS_FILE.tmp" "$STATUS_FILE"
}

write_status running "$(git -C "$APP_DIR" rev-parse HEAD 2>/dev/null || true)"
trap 'write_status failed "$(git -C "$APP_DIR" rev-parse HEAD 2>/dev/null || true)"' ERR

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
  write_status idle "$LOCAL_SHA"
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
    write_status success "$REMOTE_SHA"
    trap - ERR
    exit 0
  fi
  sleep 2
done

echo "Deploy aplicado, mas o health check não respondeu a tempo." >&2
docker compose ps >&2
write_status failed "$REMOTE_SHA"
exit 1

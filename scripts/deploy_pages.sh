#!/usr/bin/env bash
# Deploy static board (web/) + root latest.json to Cloudflare Pages.
# Reads credentials from repo-root .env (never commit .env).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

PROJECT_NAME="${CLOUDFLARE_PAGES_PROJECT:-agent-speed}"
WEB_DIR="${AGENT_SPEED_WEB_DIR:-web}"
ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID:-}"

if [[ -z "${CLOUDFLARE_API_TOKEN:-}" && -z "${CLOUDFLARE_API_KEY:-}" ]]; then
  echo "deploy_pages: missing CLOUDFLARE_API_TOKEN or CLOUDFLARE_API_KEY in .env" >&2
  exit 1
fi
if [[ -n "${CLOUDFLARE_API_KEY:-}" && -z "${CLOUDFLARE_EMAIL:-}" ]]; then
  echo "deploy_pages: CLOUDFLARE_API_KEY requires CLOUDFLARE_EMAIL in .env" >&2
  exit 1
fi
if [[ -z "$ACCOUNT_ID" ]]; then
  echo "deploy_pages: missing CLOUDFLARE_ACCOUNT_ID in .env" >&2
  exit 1
fi
if [[ ! -f "$ROOT/latest.json" ]]; then
  echo "deploy_pages: latest.json not found at repo root" >&2
  exit 1
fi
if [[ ! -f "$ROOT/$WEB_DIR/index.html" ]]; then
  echo "deploy_pages: $WEB_DIR/index.html not found" >&2
  exit 1
fi

DIST="$ROOT/.scratch/pages_dist"
rm -rf "$DIST"
mkdir -p "$DIST/logos"
cp "$ROOT/$WEB_DIR/index.html" "$DIST/"
cp "$ROOT/latest.json" "$DIST/"
if [[ -d "$ROOT/$WEB_DIR/logos" ]]; then
  cp -R "$ROOT/$WEB_DIR/logos/." "$DIST/logos/"
fi

export CLOUDFLARE_ACCOUNT_ID="$ACCOUNT_ID"
# Prefer API Token; if only Global Key is set, keep API_KEY + EMAIL and unset TOKEN.
if [[ -n "${CLOUDFLARE_API_TOKEN:-}" ]]; then
  export CLOUDFLARE_API_TOKEN
  unset CLOUDFLARE_API_KEY || true
else
  export CLOUDFLARE_API_KEY CLOUDFLARE_EMAIL
  unset CLOUDFLARE_API_TOKEN || true
fi

if command -v wrangler >/dev/null 2>&1; then
  WRANGLER=(wrangler)
elif command -v npx >/dev/null 2>&1; then
  WRANGLER=(npx --yes wrangler)
else
  echo "deploy_pages: need wrangler or npx on PATH" >&2
  exit 1
fi

echo "deploy_pages: deploying to Pages project '$PROJECT_NAME'..."
"${WRANGLER[@]}" pages deploy "$DIST" \
  --project-name="$PROJECT_NAME" \
  --commit-dirty=true

echo "deploy_pages: done"

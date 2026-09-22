#!/usr/bin/env bash
# Point this clone at .githooks (pre-push deploy when latest.json changes).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
chmod +x "$ROOT/.githooks/pre-push" "$ROOT/scripts/deploy_pages.sh"
git -C "$ROOT" config core.hooksPath .githooks
echo "install_git_hooks: core.hooksPath=.githooks"
echo "install_git_hooks: push will deploy when latest.json changes (requires .env)."

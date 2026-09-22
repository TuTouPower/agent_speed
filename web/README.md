# Public board (Cloudflare Pages)

Static frontend for https://agent-speed.pages.dev.

- Source of truth for data is repo-root `latest.json` (not a copy under `web/`).
- Local deploy: configure `.env` from `.env.example`, run `./scripts/install_git_hooks.sh` once, then `git push`. When `latest.json` changes in the push, `.githooks/pre-push` runs `scripts/deploy_pages.sh`.
- Manual deploy: `./scripts/deploy_pages.sh`

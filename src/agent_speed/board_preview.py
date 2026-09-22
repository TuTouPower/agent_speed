"""Best-effort README board preview regeneration after latest.json updates."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "screenshot_board.py"
DEFAULT_OUT = REPO_ROOT / "docs" / "board-preview-dark.png"


def refresh_board_preview(*, latest: Path | None = None, out: Path | None = None) -> Path | None:
    """Run screenshot_board.py. Returns output path on success, else None."""
    if not SCRIPT.is_file():
        print("skip board preview: scripts/screenshot_board.py missing", file=sys.stderr)
        return None
    cmd = [sys.executable, str(SCRIPT)]
    if latest is not None:
        cmd.extend(["--latest", str(latest)])
    if out is not None:
        cmd.extend(["-o", str(out)])
    try:
        res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=180)
    except Exception as e:
        print(f"skip board preview: {e}", file=sys.stderr)
        return None
    if res.returncode != 0:
        err = (res.stderr or res.stdout or "").strip()
        print(f"skip board preview: {err}", file=sys.stderr)
        return None
    if res.stdout.strip():
        print(res.stdout.strip())
    target = out or DEFAULT_OUT
    return target if target.is_file() else None

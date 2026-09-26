#!/usr/bin/env python3
"""screenshot_board.py — 截取 Agent Rank 公开榜单预览图（供 README 展示）。

复用历史 render_md.py 的 Chrome Headless + Retina + 自动裁白边思路。
优先本地 web 目录（可注入刚生成的 latest_200k.json，复制为站点的 latest.json），否则截线上站点。

用法：
  python3 scripts/screenshot_board.py
  python3 scripts/screenshot_board.py --url https://agent-rank.ooll.lol
  python3 scripts/screenshot_board.py --web-dir /path/to/web \\
      --latest data/latest_200k.json -o docs/board-preview-dark.png
"""

from __future__ import annotations

import argparse
import http.server
import os
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from PIL import Image, ImageChops

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "docs" / "board-preview-dark.png"
DEFAULT_URL = "https://agent-rank.ooll.lol/?theme=dark"
DEFAULT_LATEST = REPO_ROOT / "data" / "latest_200k.json"

CHROME_CANDIDATES = [
    os.environ.get("CHROME_BIN", ""),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome-stable") or "",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
    shutil.which("chromium-browser") or "",
]


def find_chrome() -> str:
    for c in CHROME_CANDIDATES:
        if c and Path(c).is_file():
            return c
    raise RuntimeError("未找到 Chrome / Chromium，无法截图。可设置 CHROME_BIN。")


def resolve_web_dir(explicit: str | None) -> Path | None:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser().resolve())
    env = os.environ.get("AGENT_RANK_WEB_DIR", "").strip()
    if env:
        candidates.append(Path(env).expanduser().resolve())
    candidates.append((REPO_ROOT / "web").resolve())
    for p in candidates:
        if (p / "index.html").is_file():
            return p
    return None


def crop_whitespace(src: Path, dest: Path, pad: int = 24) -> None:
    img = Image.open(src)
    bg = Image.new(img.mode, img.size, img.getpixel((0, 0)))
    diff = ImageChops.difference(img, bg)
    bbox = diff.getbbox()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if bbox:
        cropped = img.crop(
            (
                max(0, bbox[0] - pad),
                max(0, bbox[1] - pad),
                min(img.width, bbox[2] + pad),
                min(img.height, bbox[3] + pad),
            )
        )
        cropped.save(dest, "PNG")
    else:
        img.save(dest, "PNG")


def chrome_screenshot(chrome_bin: str, url: str, raw_png: Path, width: int, height: int, scale: int, budget_ms: int) -> None:
    cmd = [
        chrome_bin,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--hide-scrollbars",
        f"--force-device-scale-factor={scale}",
        f"--window-size={width},{height}",
        f"--virtual-time-budget={budget_ms}",
        f"--screenshot={raw_png}",
        url,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if not raw_png.is_file():
        err = (res.stderr or res.stdout or "").strip()
        raise RuntimeError(f"Chrome 截图失败: {err or 'no output file'}")


def serve_and_shot(
    chrome_bin: str,
    web_dir: Path,
    latest: Path | None,
    out: Path,
    width: int,
    height: int,
    scale: int,
    budget_ms: int,
) -> Path:
    with tempfile.TemporaryDirectory(prefix="agent-rank-board-") as tmp:
        tmp_dir = Path(tmp)
        # copy board assets
        for item in web_dir.iterdir():
            dest = tmp_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
        if latest and latest.is_file():
            shutil.copy2(latest, tmp_dir / "latest.json")

        index = tmp_dir / "index.html"
        if index.is_file():
            html = index.read_text(encoding="utf-8")
            boot = '<script>try{localStorage.setItem("agent-rank-theme","dark");}catch(e){}document.documentElement.setAttribute("data-theme","dark");</script>'
            if "agent-rank-theme" not in html[:800]:
                html = html.replace("<head>", "<head>" + boot, 1)
                index.write_text(html, encoding="utf-8")

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(tmp_dir), **kwargs)

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return

        with socketserver.TCPServer(("127.0.0.1", 0), Handler) as httpd:
            port = httpd.server_address[1]
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            time.sleep(0.2)
            raw = tmp_dir / "_raw.png"
            try:
                chrome_screenshot(
                    chrome_bin,
                    f"http://127.0.0.1:{port}/",
                    raw,
                    width,
                    height,
                    scale,
                    budget_ms,
                )
                crop_whitespace(raw, out)
            finally:
                httpd.shutdown()
        return out


def shot_url(
    chrome_bin: str,
    url: str,
    out: Path,
    width: int,
    height: int,
    scale: int,
    budget_ms: int,
) -> Path:
    from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
    parts = urlparse(url)
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    q.setdefault("theme", "dark")
    url = urlunparse(parts._replace(query=urlencode(q)))
    with tempfile.TemporaryDirectory(prefix="agent-rank-shot-") as tmp:
        raw = Path(tmp) / "raw.png"
        chrome_screenshot(chrome_bin, url, raw, width, height, scale, budget_ms)
        crop_whitespace(raw, out)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="截取 Agent Speed 榜单预览图")
    ap.add_argument("--url", default=DEFAULT_URL, help="线上榜单 URL（无本地 web 时使用）")
    ap.add_argument("--web-dir", default=None, help="本地 web 静态站点目录")
    ap.add_argument("--latest", default=str(DEFAULT_LATEST), help="注入到本地 web 的源榜（复制为 latest.json）")
    ap.add_argument("-o", "--out", default=str(DEFAULT_OUT), help="输出 PNG 路径")
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=2200)
    ap.add_argument("--scale", type=int, default=2, help="device scale factor（2=Retina）")
    ap.add_argument("--budget-ms", type=int, default=20000, help="Chrome virtual time budget")
    ap.add_argument("--force-url", action="store_true", help="强制截线上 URL，忽略本地 web-dir")
    args = ap.parse_args(argv)

    out = Path(args.out).resolve()
    chrome = find_chrome()
    latest = Path(args.latest).expanduser().resolve() if args.latest else None

    web_dir = None if args.force_url else resolve_web_dir(args.web_dir)
    if web_dir is not None:
        print(f"Using local web dir: {web_dir}")
        serve_and_shot(chrome, web_dir, latest if latest and latest.is_file() else None, out, args.width, args.height, args.scale, args.budget_ms)
    else:
        print(f"Using live URL: {args.url}")
        shot_url(chrome, args.url, out, args.width, args.height, args.scale, args.budget_ms)

    print(f"Wrote {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"screenshot_board failed: {e}", file=sys.stderr)
        raise SystemExit(1)

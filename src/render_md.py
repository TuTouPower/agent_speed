#!/usr/bin/env python3
"""render_md.py — 将 Markdown 基准结果渲染为现代科技感 Retina 高清长图。

利用系统原生 Chrome Headless 引擎与现代 CSS 渲染，零外部前端编译依赖。
支持表格智能排版、数值等宽对齐、渠道 Badge、速度分级高亮及自动裁切。

用法：
  python3 render_md.py bench_ctx_result.md
  python3 render_md.py bench_ctx_result.md -o runs/summary.png
  python3 render_md.py bench_ctx_result.md --open
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from PIL import Image, ImageChops

HERE = Path(__file__).resolve().parent

CHROME_CANDIDATES = [
    os.environ.get("CHROME_BIN", ""),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
]


def find_chrome() -> str:
    for c in CHROME_CANDIDATES:
        if c and Path(c).is_file():
            return c
    raise RuntimeError("未找到 Chrome / Chromium 可执行文件，无法进行网页截图。")


def format_inline(text: str) -> str:
    s = text
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s


def parse_markdown_to_html(md_text: str) -> str:
    lines = md_text.splitlines()
    body_html: list[str] = []
    in_table = False
    table_headers: list[str] = []
    table_rows: list[list[str]] = []
    in_list = False
    in_code = False
    code_block: list[str] = []

    def flush_table() -> str:
        nonlocal in_table, table_headers, table_rows
        if not in_table:
            return ""
        out = ["<div class=\"table-container\"><table>"]
        if table_headers:
            out.append("<thead><tr>")
            for h in table_headers:
                is_num = any(k in h.lower() for k in ["wall", "ttft", "in", "out", "tps", "srv", "sec", "chars"])
                align = "text-right" if is_num else "text-left"
                out.append(f"<th class=\"{align}\">{format_inline(h)}</th>")
            out.append("</tr></thead>")
        if table_rows:
            out.append("<tbody>")
            for r in table_rows:
                out.append("<tr>")
                for i, c in enumerate(r):
                    header = table_headers[i].lower() if i < len(table_headers) else ""
                    is_num = any(k in header for k in ["wall", "ttft", "in", "out", "tps", "srv", "sec", "chars"])
                    align = "text-right" if is_num else "text-left"

                    val = c
                    # 来源 Badge 徽章
                    if header == "src":
                        c_low = c.lower()
                        badge_cls = "badge-default"
                        if "opencode" in c_low:
                            badge_cls = "badge-blue"
                        elif "grok" in c_low:
                            badge_cls = "badge-purple"
                        elif "deepseek" in c_low:
                            badge_cls = "badge-cyan"
                        elif "kimi" in c_low:
                            badge_cls = "badge-green"
                        elif "step" in c_low or "阶跃" in c_low:
                            badge_cls = "badge-orange"
                        elif "codex" in c_low:
                            badge_cls = "badge-gray"
                        val = f"<span class=\"badge {badge_cls}\">{c}</span>"
                    elif header in ("tps", "tps_srv") and c not in ("-", "None", ""):
                        try:
                            f = float(c)
                            if f >= 200:
                                val = f"<span class=\"tps-top\">{c}</span>"
                            elif f >= 100:
                                val = f"<span class=\"tps-high\">{c}</span>"
                            else:
                                val = f"<span class=\"tps-normal\">{c}</span>"
                        except ValueError:
                            pass
                    elif is_num and c not in ("-", "None", ""):
                        val = f"<span class=\"num-val\">{c}</span>"
                    else:
                        val = format_inline(c)

                    out.append(f"<td class=\"{align}\">{val}</td>")
                out.append("</tr>")
            out.append("</tbody>")
        out.append("</table></div>")
        in_table = False
        table_headers = []
        table_rows = []
        return "\n".join(out)

    def flush_list() -> str:
        nonlocal in_list
        if in_list:
            in_list = False
            return "</ul>"
        return ""

    for line in lines:
        s = line.strip()

        if s.startswith("```"):
            if in_code:
                in_code = False
                body_html.append(f"<pre><code>{'\n'.join(code_block)}</code></pre>")
                code_block = []
            else:
                in_code = True
            continue
        if in_code:
            code_block.append(line)
            continue

        if s.startswith("|") and s.endswith("|"):
            if in_list:
                body_html.append(flush_list())
            cells = [c.strip() for c in s[1:-1].split("|")]
            if all(re.match(r"^:?-+:?$", c) for c in cells):
                continue
            if not in_table:
                in_table = True
                table_headers = cells
            else:
                table_rows.append(cells)
            continue
        elif in_table:
            body_html.append(flush_table())

        if s.startswith("# "):
            if in_list:
                body_html.append(flush_list())
            body_html.append(f"<h1>{format_inline(s[2:])}</h1>")
        elif s.startswith("## "):
            if in_list:
                body_html.append(flush_list())
            body_html.append(f"<h2>{format_inline(s[3:])}</h2>")
        elif s.startswith("### "):
            if in_list:
                body_html.append(flush_list())
            body_html.append(f"<h3>{format_inline(s[4:])}</h3>")
        elif s.startswith("- "):
            if not in_list:
                in_list = True
                body_html.append("<ul>")
            body_html.append(f"<li>{format_inline(s[2:])}</li>")
        elif s.startswith("> "):
            if in_list:
                body_html.append(flush_list())
            body_html.append(f"<blockquote>{format_inline(s[2:])}</blockquote>")
        elif s:
            if in_list:
                body_html.append(flush_list())
            body_html.append(f"<p>{format_inline(s)}</p>")

    if in_table:
        body_html.append(flush_table())
    if in_list:
        body_html.append(flush_list())

    return "\n".join(body_html)


CSS_STYLE = """
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 40px;
  background: #090d13;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", "PingFang SC", Helvetica, Arial, sans-serif;
  color: #e6edf3;
  display: inline-block;
  min-width: 980px;
  -webkit-font-smoothing: antialiased;
}
.card {
  position: relative;
  background: #111722;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 18px;
  padding: 36px 40px;
  box-shadow: 0 20px 48px rgba(0, 0, 0, 0.7), 0 0 0 1px rgba(255, 255, 255, 0.05);
  overflow: hidden;
}
.watermark-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 50;
  background-image: url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%20width%3D%22280%22%20height%3D%22130%22%3E%3Ctext%20x%3D%22140%22%20y%3D%2265%22%20fill%3D%22rgba%28255%2C%20255%2C%20255%2C%200.035%29%22%20font-size%3D%2213%22%20font-family%3D%22-apple-system%2C%20BlinkMacSystemFont%2C%20sans-serif%22%20font-weight%3D%22600%22%20letter-spacing%3D%221px%22%20text-anchor%3D%22middle%22%20transform%3D%22rotate%28-26%2C%20140%2C%2065%29%22%3EGitHub%3A%20TuTouPower%3C/text%3E%3C/svg%3E");
  background-repeat: repeat;
}
.github-badge {
  position: absolute;
  top: 36px;
  right: 40px;
  display: flex;
  align-items: center;
  gap: 7px;
  color: #c9d1d9;
  font-size: 13px;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif;
  background: rgba(255, 255, 255, 0.06);
  padding: 6px 14px;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  font-weight: 500;
  letter-spacing: 0.01em;
  z-index: 60;
}
.github-badge svg {
  fill: #c9d1d9;
}
h1 {
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0 0 14px 0;
  color: #f0f6fc;
  display: flex;
  align-items: center;
  gap: 12px;
}
h1::before {
  content: "";
  display: inline-block;
  width: 6px;
  height: 24px;
  background: linear-gradient(180deg, #58a6ff 0%, #1f6feb 100%);
  border-radius: 3px;
}
h2 {
  font-size: 17px;
  font-weight: 600;
  color: #c9d1d9;
  margin: 28px 0 14px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  padding-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}
p {
  font-size: 14px;
  line-height: 1.65;
  color: #8b949e;
  margin: 0 0 20px 0;
}
.table-container {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  overflow: hidden;
  margin: 16px 0 24px 0;
  background: #0d121a;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13.5px;
}
th {
  background: #151e2b;
  color: #8b949e;
  font-weight: 600;
  text-transform: uppercase;
  font-size: 11.5px;
  letter-spacing: 0.05em;
  padding: 12px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
td {
  padding: 11px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  color: #c9d1d9;
}
tr:last-child td {
  border-bottom: none;
}
tr:nth-child(even) {
  background: rgba(255, 255, 255, 0.015);
}
.text-left { text-align: left; }
.text-right {
  text-align: right;
  font-family: "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace;
}
.num-val {
  font-variant-numeric: tabular-nums;
}
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11.5px;
  font-weight: 500;
  letter-spacing: 0.02em;
}
.badge-blue { background: rgba(56, 139, 253, 0.15); color: #58a6ff; border: 1px solid rgba(56, 139, 253, 0.3); }
.badge-purple { background: rgba(187, 128, 255, 0.15); color: #bc8cff; border: 1px solid rgba(187, 128, 255, 0.3); }
.badge-cyan { background: rgba(57, 197, 207, 0.15); color: #39c5cf; border: 1px solid rgba(57, 197, 207, 0.3); }
.badge-green { background: rgba(63, 185, 80, 0.15); color: #3fb950; border: 1px solid rgba(63, 185, 80, 0.3); }
.badge-orange { background: rgba(240, 136, 62, 0.15); color: #f0883e; border: 1px solid rgba(240, 136, 62, 0.3); }
.badge-gray { background: rgba(139, 148, 158, 0.15); color: #8b949e; border: 1px solid rgba(139, 148, 158, 0.3); }
.badge-default { background: rgba(255, 255, 255, 0.08); color: #c9d1d9; }

.tps-top { color: #3fb950; font-weight: 700; }
.tps-high { color: #58a6ff; font-weight: 600; }
.tps-normal { color: #c9d1d9; font-weight: 400; }

ul {
  margin: 8px 0 16px 20px;
  padding: 0;
  color: #8b949e;
  font-size: 13.5px;
  line-height: 1.65;
}
li { margin-bottom: 5px; }
blockquote {
  margin: 12px 0;
  padding: 8px 16px;
  border-left: 3px solid #58a6ff;
  background: rgba(88, 166, 255, 0.08);
  border-radius: 0 6px 6px 0;
  color: #c9d1d9;
  font-size: 13px;
}
pre {
  background: #0d121a;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 14px 18px;
  overflow-x: auto;
  font-family: "SF Mono", Menlo, Consolas, monospace;
  font-size: 12.5px;
  color: #e6edf3;
}
code {
  font-family: "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.08);
  padding: 2px 6px;
  border-radius: 4px;
  color: #e6edf3;
}
strong { color: #f0f6fc; font-weight: 600; }
"""


def render_markdown(md_path: str | Path, out_image_path: str | Path | None = None) -> Path:
    md_file = Path(md_path).resolve()
    if not md_file.exists():
        raise FileNotFoundError(f"Markdown 文件不存在: {md_file}")

    if out_image_path is None:
        out_image = md_file.with_suffix(".png")
    else:
        out_image = Path(out_image_path).resolve()

    chrome_bin = find_chrome()
    md_text = md_file.read_text(encoding="utf-8")
    body_content = parse_markdown_to_html(md_text)

    full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>{CSS_STYLE}</style>
</head>
<body>
<div class="card">
<div class="watermark-overlay"></div>
<div class="github-badge">
  <svg height="15" width="15" viewBox="0 0 16 16" fill="currentColor">
    <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path>
  </svg>
  <span>GitHub: TuTouPower</span>
</div>
{body_content}
</div>
</body>
</html>
"""

    with tempfile.NamedTemporaryFile(suffix=".html", mode="w", encoding="utf-8", delete=False) as f:
        f.write(full_html)
        temp_html = f.name

    temp_png = temp_html + ".png"

    # --force-device-scale-factor=2 产生 2x Retina 高清图
    cmd = [
        chrome_bin,
        "--headless=new",
        "--hide-scrollbars",
        "--force-device-scale-factor=2",
        "--window-size=1200,2400",
        f"--screenshot={temp_png}",
        temp_html,
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if not os.path.exists(temp_png):
        raise RuntimeError(f"Chrome 渲染失败: {res.stderr}")

    # 自动裁切边缘多余留白
    try:
        img = Image.open(temp_png)
        bg = Image.new(img.mode, img.size, img.getpixel((0, 0)))
        diff = ImageChops.difference(img, bg)
        bbox = diff.getbbox()
        if bbox:
            pad = 32
            cropped = img.crop((
                max(0, bbox[0] - pad),
                max(0, bbox[1] - pad),
                min(img.width, bbox[2] + pad),
                min(img.height, bbox[3] + pad),
            ))
            out_image.parent.mkdir(parents=True, exist_ok=True)
            cropped.save(out_image, "PNG")
        else:
            out_image.parent.mkdir(parents=True, exist_ok=True)
            img.save(out_image, "PNG")
    finally:
        if os.path.exists(temp_png):
            os.unlink(temp_png)
        if os.path.exists(temp_html):
            os.unlink(temp_html)

    return out_image


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="渲染 Markdown 文件为 Retina 高清图")
    ap.add_argument("file", help="输入的 markdown 文件路径")
    ap.add_argument("-o", "--out", default="", help="输出的图片路径（缺省为同名 .png）")
    ap.add_argument("--open", action="store_true", help="生成后使用系统默认程序打开预览")
    args = ap.parse_args(argv)

    try:
        out_path = render_markdown(args.file, args.out or None)
        print(f"渲染成功: {out_path}")
        if args.open:
            subprocess.run(["open", str(out_path)])
        return 0
    except Exception as e:
        print(f"渲染失败: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

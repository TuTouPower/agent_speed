#!/usr/bin/env python3
"""build_fixture.py — 按 token 目标从有序文件清单组装 fixture，保证前缀可嵌套。

清单顺序即 fixture 顺序：小档位取大档位的前缀，天然嵌套。
用法：
  python3 build_fixture.py --files /tmp/files.txt --tokens 300000 \
      --out fixtures/input_300k.txt --manifest fixtures/manifest_300k.json \
      --root /path/to/source_repo
"""

import argparse
import json
import os
from pathlib import Path

import tiktoken


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", required=True)
    ap.add_argument("--tokens", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--root", default="")
    ap.add_argument("--encoding", default="cl100k_base")
    args = ap.parse_args()

    enc = tiktoken.get_encoding(args.encoding)
    root = str(Path(args.root).expanduser()) if args.root else ""
    paths = [l.strip() for l in open(args.files, encoding="utf-8") if l.strip()]

    entries = []
    total = 0
    chunks = []
    for p in paths:
        if total >= args.tokens:
            break
        try:
            with open(p, encoding="utf-8", errors="strict") as f:
                content = f.read()
        except (OSError, ValueError, UnicodeError):
            continue
        if not content.strip():
            continue
        rel = os.path.relpath(p, root) if root else p
        header = f"\n\n===== FILE: {rel} =====\n"
        body = content
        remaining = args.tokens - total
        h_toks = len(enc.encode(header))
        b_toks = len(enc.encode(body))
        if h_toks + b_toks > remaining:
            # 单文件截断补齐，截断到 token 边界
            budget = max(remaining - h_toks, 0)
            ids = enc.encode(body)[:budget]
            body = enc.decode(ids)
            truncated = True
        else:
            truncated = False
        chunk = header + body
        chunks.append(chunk)
        total += len(enc.encode(chunk))
        entries.append({"path": rel, "tokens": len(enc.encode(chunk)), "truncated": truncated})
        if truncated:
            break

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(chunks), encoding="utf-8")
    man = {"target_tokens": args.tokens, "actual_tokens": total,
           "n_files": len(entries), "encoding": args.encoding, "files": entries}
    Path(args.manifest).write_text(json.dumps(man, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"files={len(entries)} tokens={total} out={args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

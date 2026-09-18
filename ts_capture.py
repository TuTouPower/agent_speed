#!/usr/bin/env python3
"""ts_capture.py — 跑一个命令，给 stdout 每行打到达时间戳，存 jsonl供 TTFT 分析。

用法：python3 ts_capture.py <out.jsonl> -- <cmd...>
每行记录 {"t": <相对秒>, "line": <原文>}；结束附 {"t":..,"__exit__":code}。
stdin 可管道透传（用于 codex exec -）。
"""

import json
import subprocess
import sys
import time


def main() -> int:
    if "--" not in sys.argv:
        print("usage: ts_capture.py <out.jsonl> -- <cmd...>", file=sys.stderr)
        return 2
    sep = sys.argv.index("--")
    out_path = sys.argv[1]
    cmd = sys.argv[sep + 1 :]
    data = sys.stdin.read() if not sys.stdin.isatty() else None
    t0 = time.monotonic()
    recs = []
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE if data else None,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if data:
        try:
            proc.stdin.write(data)
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass
    assert proc.stdout is not None
    for line in proc.stdout:
        recs.append({"t": round(time.monotonic() - t0, 3), "line": line.rstrip("\n")})
    _, err = proc.communicate()
    recs.append({"t": round(time.monotonic() - t0, 3), "__exit__": proc.returncode,
                 "stderr_tail": (err or "")[-500:]})
    with open(out_path, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"lines={len(recs) - 1} exit={proc.returncode} out={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""build_django_corpus.py — 构建 django 6.1.1 评测切片与 manifest。

按 cl100k 计数，10K 是 100K 的前缀，100K 是 200K 的前缀。
排除 tests、migrations、locale、构建配置与二进制文件。
"""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import tiktoken

DJANGO_TAG = "6.1.1"
DJANGO_COMMIT = "249b13d6e93ee3164dee8ed1775395622a50c337"
DJANGO_REPO_URL = "https://github.com/django/django.git"

TARGET_TIERS = {
    "10k": 10000,
    "100k": 100000,
    "200k": 200000,
}

EXCLUDED_NAMES = {
    "Makefile", "make.bat", "conf.py", "lint.py", "spelling_wordlist",
    "Gruntfile.js", "package.json", "tox.ini", "biome.json", "zizmor.yml",
}

EXCLUDED_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
    ".mo", ".po", ".pyc", ".pyo", ".pyd", ".woff", ".woff2", ".ttf", ".eot",
}


def ensure_django_source(cache_dir: Path | None = None) -> Path:
    """获取并核对 django 6.1.1 源码目录。"""
    candidates = []
    if cache_dir:
        candidates.append(Path(cache_dir).expanduser().resolve())
    candidates.extend([
        Path("/var/folders/gy/lhhdcfps1r9426vydlnn1gnc0000gn/T/opencode/django_6_1_1"),
        Path.home() / "kar/github_repo/django",
        Path("/tmp/django_6_1_1"),
    ])

    for c in candidates:
        if c.exists() and (c / "django/__init__.py").exists():
            # 核验 commit hash 必须精确匹配
            res = subprocess.run(
                ["git", "-C", str(c), "rev-parse", "HEAD"],
                capture_output=True, text=True,
            )
            if res.returncode == 0 and res.stdout.strip() == DJANGO_COMMIT:
                return c

    # 克隆到 /tmp/django_6_1_1
    target = Path("/tmp/django_6_1_1")
    if target.exists():
        shutil.rmtree(target)
    print(f"Cloning django {DJANGO_TAG} ({DJANGO_COMMIT}) into {target}...")
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", DJANGO_TAG, DJANGO_REPO_URL, str(target)],
        check=True,
    )
    res = subprocess.run(
        ["git", "-C", str(target), "rev-parse", "HEAD"],
        capture_output=True, text=True,
    )
    if res.returncode != 0 or res.stdout.strip() != DJANGO_COMMIT:
        raise RuntimeError(f"Cloned commit {res.stdout.strip()} does not match pin {DJANGO_COMMIT}")
    return target


def collect_django_files(root: Path) -> list[str]:
    """收集符合过滤规则的源码与文档文件，返回相对路径列表（有序）。"""
    matched = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()

        # 仅限 django/ 与 docs/
        if not (rel.startswith("django/") or rel.startswith("docs/")):
            continue

        # 排除 tests 目录及单独的测试文件
        if (
            "/tests/" in rel
            or rel.startswith("tests/")
            or "/js_tests/" in rel
            or rel.startswith("js_tests/")
            or p.name == "tests.py"
            or p.name.startswith("test_")
            or p.name.endswith("_test.py")
            or p.name.endswith("_tests.py")
        ):
            continue

        # 排除 migrations/
        if "/migrations/" in rel or rel.startswith("migrations/"):
            continue

        # 排除 locale/
        if "/locale/" in rel or rel.startswith("locale/"):
            continue
            continue

        # 排除 locale/
        if "/locale/" in rel or rel.startswith("locale/"):
            continue

        # 排除文件名与后缀
        if p.name in EXCLUDED_NAMES:
            continue
        if p.suffix.lower() in EXCLUDED_EXTS:
            continue

        # 源码限定 .py，文档限定 .txt / .rst
        if rel.startswith("django/") and p.suffix.lower() != ".py":
            continue
        if rel.startswith("docs/") and p.suffix.lower() not in [".txt", ".rst"]:
            continue

        matched.append(rel)

    matched.sort()
    return matched


def build_slices(root: Path, rel_paths: list[str], fixtures_dir: Path):
    """组装 10k, 100k, 200k 三档切片与 manifest。"""
    enc = tiktoken.get_encoding("cl100k_base")

    # 累加文件块直到超过 200,000 tokens
    file_chunks = []
    total_tokens_approx = 0
    max_target = max(TARGET_TIERS.values())

    for rel in rel_paths:
        file_path = root / rel
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if not content.strip():
            continue
        chunk = f"\n\n===== FILE: {rel} =====\n{content}"
        chunk_tokens = len(enc.encode(chunk))
        file_chunks.append((rel, chunk, chunk_tokens))
        total_tokens_approx += chunk_tokens
        if total_tokens_approx >= max_target + 10000:
            break

    full_text = "".join(item[1] for item in file_chunks)
    full_tokens = enc.encode(full_text)

    fixtures_dir.mkdir(parents=True, exist_ok=True)

    header_re = re.compile(r"\n\n===== FILE: (.*?) =====\n")

    for tier_name, target_toks in TARGET_TIERS.items():
        slice_tokens = full_tokens[:target_toks]
        slice_text = enc.decode(slice_tokens)
        actual_toks = len(enc.encode(slice_text))

        # 极端情况若 token 重组有微小偏差，进行二分校准
        if actual_toks != target_toks:
            low, high = target_toks - 20, target_toks + 20
            for candidate_len in range(low, high + 1):
                cand_text = enc.decode(full_tokens[:candidate_len])
                if len(enc.encode(cand_text)) == target_toks:
                    slice_text = cand_text
                    actual_toks = target_toks
                    break

        assert actual_toks == target_toks, f"{tier_name} token count mismatch: {actual_toks} != {target_toks}"

        # 写入切片正文
        out_txt = fixtures_dir / f"django_{tier_name}.txt"
        out_txt.write_text(slice_text, encoding="utf-8")

        # 分析 manifest 包含的文件与截断状态
        matches = list(header_re.finditer(slice_text))
        entries = []
        for i, m in enumerate(matches):
            rel = m.group(1)
            start_pos = m.start()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(slice_text)
            chunk_str = slice_text[start_pos:end_pos]
            chunk_tokens = len(enc.encode(chunk_str))
            is_last = (i == len(matches) - 1)
            entries.append({
                "path": rel,
                "tokens": chunk_tokens,
                "truncated": is_last,
            })

        manifest_data = {
            "source": "django/django",
            "tag": DJANGO_TAG,
            "commit": DJANGO_COMMIT,
            "target_tokens": target_toks,
            "actual_tokens": actual_toks,
            "n_files": len(entries),
            "encoding": "cl100k_base",
            "files": entries,
        }
        out_man = fixtures_dir / f"django_{tier_name}_manifest.json"
        out_man.write_text(json.dumps(manifest_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Built {tier_name}: {out_txt.name} ({actual_toks} tokens, {len(entries)} files)")

    # 建立软链接兼容
    for tier in TARGET_TIERS:
        link_txt = fixtures_dir / f"input_{tier}.txt"
        target_txt = Path(f"django_{tier}.txt")
        if link_txt.exists() or link_txt.is_symlink():
            link_txt.unlink()
        link_txt.symlink_to(target_txt)

        link_man = fixtures_dir / f"manifest_{tier}.json"
        target_man = Path(f"django_{tier}_manifest.json")
        if link_man.exists() or link_man.is_symlink():
            link_man.unlink()
        link_man.symlink_to(target_man)


def main() -> int:
    ap = argparse.ArgumentParser(description="构建 Django 评测切片")
    ap.add_argument("--django-dir", default="", help="本地 django 源码目录（若无则自动获取）")
    ap.add_argument("--out-dir", default="fixtures", help="输出目录（默认 fixtures）")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    fixtures_dir = (repo_root / args.out_dir).resolve()
    django_root = ensure_django_source(Path(args.django_dir) if args.django_dir else None)

    print(f"Django source directory: {django_root}")
    rel_files = collect_django_files(django_root)
    print(f"Collected {len(rel_files)} eligible files from Django {DJANGO_TAG}")

    build_slices(django_root, rel_files, fixtures_dir)

    # 复制/同步 task_200k.md 到 fixtures/task_200k.md
    task_src = repo_root / "prompts/task_200k.md"
    task_dst = fixtures_dir / "task_200k.md"
    if task_src.exists():
        shutil.copy2(task_src, task_dst)
        print(f"Copied {task_src} to {task_dst}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

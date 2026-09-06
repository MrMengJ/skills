#!/usr/bin/env python3
"""Phase Δ sha256 冲突检测工具。

用法：
  python3 delta-conflicts.py check --meta-dir <path> --wiki-root <path>
  python3 delta-conflicts.py hash  --file <wiki页面.md>

  check   读取 wiki 文件、normalize、计算 sha256、与 schema 比对
  hash    输出单个文件 normalize 后的 sha256（供 update-page 使用）
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


def normalize_content(raw_bytes):
    """统一行尾为 LF，去 UTF-8 BOM，去末尾空白行。（normalization_protocol_version = v1）"""
    text = raw_bytes.decode("utf-8-sig")          # 去 BOM
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.rstrip("\n")                       # 去末尾空白行（保留内容）
    return text.encode("utf-8")


def sha256_of_normalized(path):
    return hashlib.sha256(normalize_content(Path(path).read_bytes())).hexdigest()


def sha256_no_whitespace(path):
    text = normalize_content(Path(path).read_bytes()).decode("utf-8")
    return hashlib.sha256(re.sub(r"\s+", "", text).encode("utf-8")).hexdigest()


# ─── 子命令 ──────────────────────────────────────────────────────────────────

def cmd_check(args):
    meta_dir = Path(args.meta_dir)
    wiki_root = Path(args.wiki_root)
    pages_dir = meta_dir / "pages"

    conflicts, clean, unhashed = [], [], []
    if not pages_dir.exists():
        print(json.dumps({"ok": True, "conflicts": [], "clean": []}))
        return

    for page_file in sorted(pages_dir.rglob("*.json")):
        try:
            page_data = json.loads(page_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(page_data, dict):
            continue
        page_rel = page_file.relative_to(pages_dir).with_suffix(".md").as_posix()
        meta_rel = page_file.relative_to(meta_dir).as_posix()
        schema_sha = page_data.get("content_sha256_normalized")
        wiki_file = wiki_root / page_rel

        if not wiki_file.exists():
            conflicts.append({"page": page_rel, "page_meta": meta_rel, "reason": "missing_wiki_file",
                              "schema_sha256": schema_sha, "current_sha256": None})
            continue
        if not schema_sha:
            unhashed.append(page_rel)
            continue
        current_sha = sha256_of_normalized(wiki_file)
        if current_sha == schema_sha:
            clean.append(page_rel)
        else:
            # schema 只存了 normalize 后的 sha，无法反推原文，因此纯空白改动只能在
            # 同时记录了 content_sha256_no_whitespace 时才判定；缺该字段时置 null 交给人确认。
            recorded_nows = page_data.get("content_sha256_no_whitespace")
            if recorded_nows:
                ws_only = sha256_no_whitespace(wiki_file) == recorded_nows
            else:
                ws_only = None
            conflicts.append({"page": page_rel, "page_meta": meta_rel, "reason": "manually_edited",
                              "current_sha256": current_sha, "schema_sha256": schema_sha,
                              "is_whitespace_only": ws_only})

    out = {"ok": len(conflicts) == 0, "conflicts": conflicts, "clean": clean}
    if unhashed:
        out["unhashed"] = unhashed
    print(json.dumps(out, ensure_ascii=False))


def cmd_hash(args):
    p = Path(args.file)
    if not p.exists():
        print(f"文件不存在: {p}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps({"file": str(p), "sha256": sha256_of_normalized(p),
                      "sha256_no_whitespace": sha256_no_whitespace(p),
                      "normalization_protocol_version": "v1"}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Phase Δ sha256 冲突检测工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check", help="检测 wiki 文件与 schema 记录的 sha256 是否一致")
    p.add_argument("--meta-dir", required=True)
    p.add_argument("--wiki-root", required=True)

    p = sub.add_parser("hash", help="输出单个文件 normalize 后的 sha256")
    p.add_argument("--file", required=True)

    args = parser.parse_args()
    {"check": cmd_check, "hash": cmd_hash}[args.cmd](args)


if __name__ == "__main__":
    main()

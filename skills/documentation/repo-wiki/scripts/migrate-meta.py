#!/usr/bin/env python3
"""迁移 .wiki-meta schema 版本。

用法：
  python3 migrate-meta.py --from-version 1 --to-version 2 --meta-file <v1 单文件 json> [--out-dir <.wiki-meta>]
  python3 migrate-meta.py --from-version 2 --to-version 2 --meta-dir <.wiki-meta>   # 就地规范化（补缺省字段）

v1 → v2：v1 为单文件（顶层字段 + "pages": {"<章>/<页>.md": {...}}）；v2 拆为 index.json + pages/**.json。
v2 → v2：为 v2.0 扁平 wiki 补齐 v2.1 可选字段（template_versions / run_config / _comment），不移动页面文件。
兼容矩阵与 schema 定义见 SKILL.md「兼容矩阵」与 references/meta-schema.json。
"""
import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

DEFAULT_TEMPLATE_VERSIONS = {"conceptual": 2, "reference": 2, "mixed": 2, "decision-log": 2}
COMMENT = "常用命令: /repo-wiki --update 增量更新 | /repo-wiki --rebuild 重建 | /repo-wiki --dry-run 演练"


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def migrate_1_to_2(meta_file, out_dir):
    src = json.loads(Path(meta_file).read_text(encoding="utf-8"))
    pages = src.pop("pages", {}) or {}
    index = dict(src)
    index["schema_version"] = 2
    index.setdefault("generated_at", _dt.datetime.now().astimezone().replace(microsecond=0).isoformat())
    index.setdefault("last_synced_commit", src.get("commit", "HEAD"))
    index.setdefault("primary_type", src.get("project_type", "other"))
    index.setdefault("wiki_root", src.get("output_dir", "./.wiki/"))
    index.setdefault("is_fork", bool(src.get("fork", False)))
    index.setdefault("audience", {"primary": src.get("audience", "maintainer"), "secondary": []})
    if isinstance(index["audience"], str):
        index["audience"] = {"primary": index["audience"], "secondary": []}
    index.setdefault("output_language", src.get("language", "zh-CN"))
    index.setdefault("template_versions", dict(DEFAULT_TEMPLATE_VERSIONS))
    index.setdefault("_comment", COMMENT)
    for k in ("commit", "project_type", "output_dir", "fork", "language"):
        index.pop(k, None)
    dump(out_dir / "index.json", index)

    count = 0
    for page_path, meta in pages.items():
        rel = page_path[:-3] if page_path.endswith(".md") else page_path
        page = {
            "source_files": [
                sf if isinstance(sf, dict) else {"path": sf, "role": "primary"}
                for sf in (meta.get("source_files") or meta.get("sources") or [])
            ] or [{"path": "UNKNOWN", "role": "primary"}],
            "page_type": meta.get("page_type", meta.get("type", "conceptual")),
            "template_version": int(meta.get("template_version", 1)),
            "status": meta.get("status", "active"),
        }
        for k in ("content_sha256_normalized", "normalization_protocol_version", "anchor_material", "anchor_commits"):
            if k in meta:
                page[k] = meta[k]
        dump(out_dir / "pages" / (rel + ".json"), page)
        count += 1
    print(json.dumps({"ok": True, "index": str(out_dir / "index.json"), "pages": count}, ensure_ascii=False))


def normalize_2(meta_dir):
    index_path = meta_dir / "index.json"
    if not index_path.exists():
        print(f"index.json 不存在: {index_path}", file=sys.stderr)
        sys.exit(1)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    changed = []
    if index.get("schema_version") != 2:
        index["schema_version"] = 2; changed.append("schema_version")
    if "template_versions" not in index:
        index["template_versions"] = dict(DEFAULT_TEMPLATE_VERSIONS); changed.append("template_versions")
    if "run_config" not in index:
        index["run_config"] = {"pause_between_rounds": "always", "mermaid_enabled": True}; changed.append("run_config")
    if "_comment" not in index:
        index["_comment"] = COMMENT; changed.append("_comment")
    fixed_pages = 0
    for f in (meta_dir / "pages").rglob("*.json") if (meta_dir / "pages").exists() else []:
        page = json.loads(f.read_text(encoding="utf-8"))
        touched = False
        if "template_version" not in page:
            page["template_version"] = 1; touched = True
        if "status" not in page:
            page["status"] = "active"; touched = True
        for sf in page.get("source_files", []) or []:
            if isinstance(sf, dict) and sf.get("role") == "secondary":
                sf["role"] = "supporting"; touched = True
        if touched:
            dump(f, page); fixed_pages += 1
    if changed:
        dump(index_path, index)
    print(json.dumps({"ok": True, "index_fields_added": changed, "pages_fixed": fixed_pages}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="迁移 .wiki-meta schema 版本")
    parser.add_argument("--from-version", type=int, required=True)
    parser.add_argument("--to-version", type=int, required=True)
    parser.add_argument("--meta-file", help="v1 单文件路径")
    parser.add_argument("--meta-dir", help="v2 目录路径")
    parser.add_argument("--out-dir", help="v1→v2 输出目录（默认与 meta-file 同级的 .wiki-meta/）")
    args = parser.parse_args()

    if (args.from_version, args.to_version) == (1, 2):
        if not args.meta_file:
            print("v1→v2 需要 --meta-file", file=sys.stderr); sys.exit(1)
        out = Path(args.out_dir) if args.out_dir else Path(args.meta_file).resolve().parent / ".wiki-meta"
        migrate_1_to_2(args.meta_file, out)
    elif (args.from_version, args.to_version) == (2, 2):
        if not args.meta_dir:
            print("v2→v2 需要 --meta-dir", file=sys.stderr); sys.exit(1)
        normalize_2(Path(args.meta_dir))
    else:
        print(f"不支持的迁移路径 {args.from_version}→{args.to_version}（支持 1→2、2→2）", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

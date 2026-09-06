#!/usr/bin/env python3
"""Phase Δ .wiki-meta schema 校验 / 读写 / staging 事务工具。

子命令（均输出单行 JSON 到 stdout）：
  validate         校验 index.json + pages/*.json；报告 staging 残留；可选 --repo-root 检查 source_files 存在性
  read             输出 {"index": ..., "pages": {...}}
  write-staging    从 stdin 读取新 index.json 内容写到 index.json.staging
  commit-staging   原子地把 staging 替换为 index.json，并合并 .followup-*.md
  rollback-staging 删除 staging 文件（保留 index.json 不变）
  update-page      更新单页 content_sha256_normalized + template_version（幂等）
  update-sync      写入 last_synced_commit / last_synced_branch

exit code 约定：exit 0 + "ok": false = 业务问题（需交互决策）；exit 1 = 脚本错误。
"""
import argparse
import datetime as _dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SUPPORTED_SCHEMA_VERSION = 2
SUPPORTED_TEMPLATE_VERSIONS = {"conceptual": 2, "reference": 2, "mixed": 2, "decision-log": 2}
INDEX_REQUIRED = ["schema_version", "generated_at", "last_synced_commit", "primary_type",
                  "wiki_root", "is_fork", "audience", "output_language"]
PAGE_REQUIRED = ["source_files", "page_type", "template_version", "status"]
PAGE_TYPES = {"conceptual", "reference", "mixed", "decision-log"}
ROLES = {"primary", "supporting"}
ROLE_ALIASES = {"secondary": "supporting"}  # 2026-07 期间生成的 wiki 用了 secondary
VALID_ROLES = ROLES | set(ROLE_ALIASES)
STATUSES = {"active", "deprecated"}
AUDIENCES = {"maintainer", "user", "newcomer", "business"}


def _type_err(value, expected, path):
    checks = {
        "string": lambda v: isinstance(v, str),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
        "array": lambda v: isinstance(v, list),
        "object": lambda v: isinstance(v, dict),
    }
    if not checks[expected](value):
        return {"type": "type_error", "detail": f"{path}: expected {expected}, got {type(value).__name__}"}
    return None


def _validate_index(data):
    errors = []
    for field in INDEX_REQUIRED:
        if field not in data:
            errors.append({"type": "missing_field", "field": "/" + field})
    typed = {"schema_version": "integer", "generated_at": "string", "last_synced_commit": "string",
             "last_synced_branch": "string", "primary_type": "string", "secondary_types": "array",
             "wiki_root": "string", "is_fork": "boolean", "audience": "object", "output_language": "string",
             "template_versions": "object", "ignore_patterns": "array", "chapters": "array",
             "run_config": "object", "target_pages": "integer"}
    for field, expected in typed.items():
        if field in data:
            e = _type_err(data[field], expected, "/" + field)
            if e:
                errors.append(e)
    aud = data.get("audience")
    if isinstance(aud, dict):
        if "primary" not in aud:
            errors.append({"type": "missing_field", "field": "/audience/primary"})
        elif aud["primary"] not in AUDIENCES:
            errors.append({"type": "type_error", "detail": f"/audience/primary: enum {sorted(AUDIENCES)}"})
    if isinstance(data.get("chapters"), list):
        for i, ch in enumerate(data["chapters"]):
            if not isinstance(ch, dict):
                errors.append({"type": "type_error", "detail": f"/chapters/{i}: expected object"})
                continue
            for f in ("id", "title", "type", "target_pages"):
                if f not in ch:
                    errors.append({"type": "missing_field", "field": f"/chapters/{i}/{f}"})
            if ch.get("type") not in PAGE_TYPES and "type" in ch:
                errors.append({"type": "type_error", "detail": f"/chapters/{i}/type: enum {sorted(PAGE_TYPES)}"})
            cd = ch.get("chapter_dir")
            if isinstance(cd, str) and not re.match(r"^[0-9]{2}-", cd):
                errors.append({"type": "type_error", "detail": f"/chapters/{i}/chapter_dir: 须为 NN-开头"})
    return errors


def _validate_page(data, path_prefix):
    errors = []
    if not isinstance(data, dict):
        return [{"type": "type_error", "detail": f"{path_prefix}: expected object"}]
    for field in PAGE_REQUIRED:
        if field not in data:
            errors.append({"type": "missing_field", "field": path_prefix + "/" + field})
            continue
        if field == "source_files":
            e = _type_err(data[field], "array", path_prefix + "/source_files")
            if e:
                errors.append(e)
            elif len(data[field]) == 0:
                errors.append({"type": "type_error", "detail": path_prefix + "/source_files: minItems 1"})
            else:
                for i, sf in enumerate(data[field]):
                    if not isinstance(sf, dict):
                        errors.append({"type": "type_error",
                                       "detail": f"{path_prefix}/source_files/{i}: expected object"})
                        continue
                    if not isinstance(sf.get("path"), str):
                        errors.append({"type": "missing_field" if "path" not in sf else "type_error",
                                       "field": f"{path_prefix}/source_files/{i}/path"})
                    if sf.get("role") not in VALID_ROLES:
                        errors.append({"type": "missing_field" if "role" not in sf else "type_error",
                                       "field": f"{path_prefix}/source_files/{i}/role"})
        elif field == "page_type" and data[field] not in PAGE_TYPES:
            errors.append({"type": "type_error", "detail": f"{path_prefix}/page_type: enum {sorted(PAGE_TYPES)}"})
        elif field == "template_version":
            e = _type_err(data[field], "integer", path_prefix + "/template_version")
            if e:
                errors.append(e)
        elif field == "status" and data[field] not in STATUSES:
            errors.append({"type": "type_error", "detail": f"{path_prefix}/status: enum {sorted(STATUSES)}"})
    return errors


# ─── 共用 meta 加载 ──────────────────────────────────────────────────────────

def _load_meta(meta_dir):
    """返回 (index_dict, pages_dict, error_str)。pages 的 key 形如 pages/<受众>/<章>/<页>.json。"""
    meta_dir = Path(meta_dir)
    index_path = meta_dir / "index.json"
    if not index_path.exists():
        return None, None, f"index.json 不存在: {index_path}"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return None, None, f"index.json JSON 语法错误: {e}"

    pages = {}
    pages_dir = meta_dir / "pages"
    if pages_dir.exists():
        for page_file in sorted(pages_dir.rglob("*.json")):
            rel = page_file.relative_to(meta_dir).as_posix()
            try:
                pages[rel] = json.loads(page_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                return index, pages, f"{rel} JSON 语法错误: {e}"
    return index, pages, None


def _staging_residue(meta_dir):
    meta_dir = Path(meta_dir)
    return any([(meta_dir / "index.json.staging").exists(), bool(list(meta_dir.glob("staging-*.json")))])


def _wiki_root_for(meta_dir, index):
    """wiki 根目录：v2.1 布局下 .wiki-meta 位于 wiki 根内；否则按 index.wiki_root 相对 cwd 解析。"""
    meta_dir = Path(meta_dir).resolve()
    if meta_dir.name == ".wiki-meta" and (meta_dir.parent / "INDEX.md").exists():
        return meta_dir.parent
    wr = (index or {}).get("wiki_root")
    if wr:
        p = Path(wr)
        return p if p.is_absolute() else (Path.cwd() / p).resolve()
    return meta_dir.parent


# ─── 子命令实现 ──────────────────────────────────────────────────────────────

def cmd_validate(args):
    meta_dir = Path(args.meta_dir)
    errors = []
    notes = []
    alias_pages = set()
    staging_residue = _staging_residue(meta_dir)

    index, pages, load_err = _load_meta(meta_dir)
    if load_err:
        print(json.dumps({"ok": False, "errors": [{"type": "json_syntax", "detail": load_err}],
                          "staging_residue": staging_residue}, ensure_ascii=False))
        return
    if index is None:
        print(json.dumps({"ok": False, "errors": [{"type": "missing_index"}],
                          "staging_residue": staging_residue}, ensure_ascii=False))
        return

    sv = index.get("schema_version", 0)
    if isinstance(sv, int) and sv > SUPPORTED_SCHEMA_VERSION:
        errors.append({"type": "schema_version_ahead", "schema_version": sv,
                       "supported": SUPPORTED_SCHEMA_VERSION, "action": "run_migrate_meta"})

    errors.extend(_validate_index(index))

    base = index.get("last_synced_commit")
    if isinstance(base, str) and not re.fullmatch(r"[0-9a-f]{40}", base.strip()):
        errors.append({
            "type": "symbolic_base",
            "last_synced_commit": base,
            "detail": "last_synced_commit 必须是完整 40 位 commit hash；符号引用（HEAD / 分支名 / 短 hash）会让 Phase Δ 的 diff 恒为空",
            "options": ["resolve", "specify", "rebuild"],
        })

    repo_root = Path(args.repo_root).resolve() if args.repo_root else None
    if repo_root is None and index.get("source_root"):
        # 相对 wiki 根目录解析。<项目>/.wiki 这种常见布局对应 ".."
        repo_root = (_wiki_root_for(meta_dir, index) / index["source_root"]).resolve()
    checked_paths = missing_paths = 0
    for page_rel, page_data in (pages or {}).items():
        page_errors = _validate_page(page_data, "/" + page_rel)
        errors.extend(page_errors)
        # 别名检测与路径无关，必须在 repo_root 守卫之前做
        if isinstance(page_data, dict):
            for sf in page_data.get("source_files", []) or []:
                if isinstance(sf, dict) and sf.get("role") in ROLE_ALIASES:
                    alias_pages.add(page_rel)
        if repo_root is None or page_errors or not isinstance(page_data, dict):
            continue
        for sf in page_data.get("source_files", []):
            p = sf.get("path") if isinstance(sf, dict) else None
            if not (isinstance(p, str) and p):
                continue
            role = sf.get("role") if isinstance(sf, dict) else None
            role = ROLE_ALIASES.get(role, role)
            target = repo_root / p
            if target.is_dir():
                # 目录不会出现在 git diff 的文件列表里。作为 primary 是硬伤：这一页永远不会被判为
                # 受影响（静默假阴性）。作为 supporting 只是失去提示能力，「目录地图」类页面这样写
                # 是合理的，因此只记 note 不报错。
                if role == "primary":
                    errors.append({"type": "source_is_directory", "page": page_rel, "path": p,
                                   "detail": "primary 源必须是具体文件；目录不出现在 git diff 的文件列表里，"
                                             "这一页将永远不会被标记为受影响",
                                   "options": ["expand", "typo", "skip"]})
                else:
                    notes.append({"type": "supporting_source_is_directory", "page": page_rel, "path": p,
                                  "detail": "supporting 源写成目录：不影响重写判定，但该路径不会产生任何提示"})
            else:
                checked_paths += 1
                if not target.is_file():
                    missing_paths += 1
                    errors.append({"type": "missing_source_file", "page": page_rel, "path": p,
                                   "options": ["renamed", "deleted", "typo", "skip"]})

    for tname, tver in (index.get("template_versions") or {}).items():
        supported = SUPPORTED_TEMPLATE_VERSIONS.get(tname, 0)
        if supported and isinstance(tver, int) and tver > supported:
            errors.append({"type": "template_version_ahead", "template": tname,
                           "version": tver, "supported": supported})

    if checked_paths and missing_paths > checked_paths * 0.5:
        notes.append({"type": "source_root_mismatch", "missing": missing_paths, "checked": checked_paths,
                      "detail": f"{missing_paths}/{checked_paths} 个源码路径都找不到，多半是 --repo-root 给错了"
                                "（工作区级 wiki 的 source_files 常相对工作区根而非单个仓库根），"
                                "先确认根目录再逐条处理 missing_source_file；确认后把 source_root 写进 index.json"})
    if alias_pages:
        notes.append({"type": "deprecated_role_alias", "count": len(alias_pages),
                      "detail": 'role 用了历史别名 "secondary"（等价于 "supporting"）。脚本已兼容，'
                                "但建议运行 migrate-meta.py --from-version 2 --to-version 2 统一改写"})
    out = {"ok": len(errors) == 0, "errors": errors, "staging_residue": staging_residue}
    if notes:
        out["notes"] = notes
    print(json.dumps(out, ensure_ascii=False))


def cmd_read(args):
    index, pages, load_err = _load_meta(args.meta_dir)
    if load_err:
        print(json.dumps({"error": load_err}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    print(json.dumps({"index": index, "pages": pages or {}}, ensure_ascii=False))


def cmd_write_staging(args):
    meta_dir = Path(args.meta_dir)
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "errors": [{"type": "json_syntax", "detail": str(e)}]}, ensure_ascii=False))
        return
    errors = _validate_index(data)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False))
        return
    meta_dir.mkdir(parents=True, exist_ok=True)
    staging = meta_dir / "index.json.staging"
    staging.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "staging": str(staging)}, ensure_ascii=False))


def _merge_followups(wiki_root):
    """把 .followup-<agent-id>.md 合并进 .followup.md 并删除临时文件；返回合并数。"""
    merged = 0
    if not wiki_root.is_dir():
        return 0
    target = wiki_root / ".followup.md"
    parts = sorted(p for p in wiki_root.glob(".followup-*.md") if p.name != ".followup.md")
    if not parts:
        return 0
    chunks = [target.read_text(encoding="utf-8").rstrip("\n")] if target.exists() else ["# 补读待办"]
    for p in parts:
        body = p.read_text(encoding="utf-8").strip()
        if body:
            chunks.append(f"\n<!-- merged from {p.name} -->\n{body}")
        p.unlink()
        merged += 1
    target.write_text("\n".join(chunks).rstrip("\n") + "\n", encoding="utf-8")
    return merged


def cmd_commit_staging(args):
    meta_dir = Path(args.meta_dir)
    staging = meta_dir / "index.json.staging"
    if not staging.exists():
        print(json.dumps({"ok": False, "errors": [{"type": "no_staging", "detail": f"{staging} 不存在"}]},
                         ensure_ascii=False))
        return
    try:
        data = json.loads(staging.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "errors": [{"type": "json_syntax", "detail": str(e)}]}, ensure_ascii=False))
        return
    os.replace(staging, meta_dir / "index.json")  # 同一目录内 rename，原子
    merged = _merge_followups(_wiki_root_for(meta_dir, data))
    out = {"ok": True}
    if merged:
        out["followups_merged"] = merged
    print(json.dumps(out, ensure_ascii=False))


def cmd_rollback_staging(args):
    meta_dir = Path(args.meta_dir)
    staging_path = meta_dir / "index.json.staging"
    if staging_path.exists():
        if args.keep:
            debug = staging_path.with_name(f"staging-{_dt.datetime.now():%Y%m%d-%H%M%S}.json")
            os.replace(staging_path, debug)
            print(json.dumps({"ok": True, "deleted": None, "kept": str(debug)}, ensure_ascii=False))
            return
        staging_path.unlink()
        print(json.dumps({"ok": True, "deleted": str(staging_path)}, ensure_ascii=False))
    else:
        print(json.dumps({"ok": True, "deleted": None}, ensure_ascii=False))


def cmd_update_page(args):
    meta_dir = Path(args.meta_dir)
    page = args.page if args.page.startswith("pages/") else "pages/" + args.page
    if not page.endswith(".json"):
        page += ".json"
    page_path = meta_dir / page
    if not page_path.exists():
        print(f"页面文件不存在: {page_path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(page_path.read_text(encoding="utf-8"))
    changed = False
    if args.sha256 is not None and data.get("content_sha256_normalized") != args.sha256:
        data["content_sha256_normalized"] = args.sha256
        data["normalization_protocol_version"] = "v1"
        changed = True
    if args.template_version is not None and data.get("template_version") != args.template_version:
        data["template_version"] = args.template_version
        changed = True
    if args.status is not None and data.get("status") != args.status:
        data["status"] = args.status
        changed = True
    if changed:
        page_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "changed": changed}, ensure_ascii=False))


def _git(args_list, cwd=None):
    r = subprocess.run(["git"] + args_list, cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def cmd_update_sync(args):
    meta_dir = Path(args.meta_dir)
    index_path = meta_dir / "index.json"
    if not index_path.exists():
        print(f"index.json 不存在: {index_path}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(index_path.read_text(encoding="utf-8"))
    repo_root = args.repo_root or None
    commit = args.commit
    code, full, err = _git(["rev-parse", "--verify", commit + "^{commit}"], cwd=repo_root)
    if code == 0 and full:
        commit = full
    elif commit == "HEAD":
        print(json.dumps({"ok": False, "errors": [{"type": "git_error", "detail": err or "无法解析 HEAD"}]},
                         ensure_ascii=False))
        return
    branch = args.branch
    if not branch:
        code, cur, _ = _git(["branch", "--show-current"], cwd=repo_root)
        branch = cur if code == 0 and cur else data.get("last_synced_branch", "")
    data["last_synced_commit"] = commit
    if branch:
        data["last_synced_branch"] = branch
    data["last_synced_at"] = _dt.datetime.now().astimezone().replace(microsecond=0).isoformat()
    index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Phase Δ .wiki-meta schema 工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("validate", help="校验 index.json 与 pages/*.json")
    p.add_argument("--meta-dir", required=True)
    p.add_argument("--repo-root", help="给定时检查 source_files 路径是否存在")

    p = sub.add_parser("read", help="输出 index + pages")
    p.add_argument("--meta-dir", required=True)

    p = sub.add_parser("write-staging", help="从 stdin 写入 index.json.staging")
    p.add_argument("--meta-dir", required=True)

    p = sub.add_parser("commit-staging", help="staging → index.json（原子）并合并 .followup-*.md")
    p.add_argument("--meta-dir", required=True)

    p = sub.add_parser("rollback-staging", help="删除 staging 文件")
    p.add_argument("--meta-dir", required=True)
    p.add_argument("--keep", action="store_true", help="改名为 staging-<ts>.json 保留供 debug")

    p = sub.add_parser("update-page", help="更新单页 sha256 / template_version / status（幂等）")
    p.add_argument("--meta-dir", required=True)
    p.add_argument("--page", required=True, help="相对 meta-dir 的页面 json 路径，pages/ 前缀可省略")
    p.add_argument("--sha256")
    p.add_argument("--template-version", type=int)
    p.add_argument("--status", choices=sorted(STATUSES))

    p = sub.add_parser("update-sync", help="写入 last_synced_commit / last_synced_branch")
    p.add_argument("--meta-dir", required=True)
    p.add_argument("--commit", default="HEAD")
    p.add_argument("--branch")
    p.add_argument("--repo-root")

    args = parser.parse_args()
    {
        "validate": cmd_validate,
        "read": cmd_read,
        "write-staging": cmd_write_staging,
        "commit-staging": cmd_commit_staging,
        "rollback-staging": cmd_rollback_staging,
        "update-page": cmd_update_page,
        "update-sync": cmd_update_sync,
    }[args.cmd](args)


if __name__ == "__main__":
    main()

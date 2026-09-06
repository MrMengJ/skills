#!/usr/bin/env python3
"""Phase Δ git 操作工具：预检 / 差异收集 / 反向映射 / 孤儿扫描。

子命令（均输出单行 JSON 到 stdout）：
  precheck        --meta-dir <p> [--repo-root <p>]                → ok, issues[]
  collect         --base <commit> [--head HEAD] [--repo-root <p>] → added, modified, deleted, renamed, split_candidates
  affected-pages  --meta-dir <p> --base <commit> [--repo-root <p>] → primary, supporting, deprecated (+truncated/total)
  orphan-scan     --meta-dir <p> --repo-root <p> [--ignore-patterns <json|逗号分隔>] → orphans[], clusters[]

exit code 约定：exit 0 + "ok": false = 业务问题（需交互决策）；exit 1 = 脚本错误。
"""
import argparse
import fnmatch
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

TRUNCATE_LIMIT = 50          # affected-pages 总条数上限（超出时给 truncated + total）
ORPHAN_LIMIT = 200           # orphan-scan 明细上限
CLUSTER_MIN = 5              # 同目录孤儿 ≥ N 个归为一簇

DEFAULT_IGNORE = {
    "typescript": ["*.test.*", "*.spec.*", "*.d.ts", "__mocks__/**", "**/__snapshots__/**", "node_modules/**"],
    "javascript": ["*.test.*", "*.spec.*", "*.d.ts", "__mocks__/**", "**/__snapshots__/**", "node_modules/**"],
    "python": ["**/test_*.py", "**/*_test.py", "**/tests/**", "**/__pycache__/**", "**/conftest.py"],
    "go": ["**/*_test.go", "**/testdata/**", "**/vendor/**"],
    "rust": ["**/target/**", "**/tests/**"],
    "java": ["**/test/**", "**/build/**", "**/target/**"],
}
COMMON_IGNORE = [".git/**", "dist/**", "build/**", "*.log", ".DS_Store"]


# ─── 基础工具 ────────────────────────────────────────────────────────────────

def _git(args_list, cwd, check=False):
    r = subprocess.run(["git"] + args_list, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        print(f"git {' '.join(args_list)} 失败: {r.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return r.returncode, r.stdout, r.stderr.strip()


def _repo_root(arg):
    root = Path(arg).resolve() if arg else Path.cwd()
    code, out, _ = _git(["rev-parse", "--show-toplevel"], cwd=root)
    if code != 0:
        return root, False
    return Path(out.strip()), True


def _load_index(meta_dir):
    p = Path(meta_dir) / "index.json"
    if not p.exists():
        print(f"index.json 不存在: {p}", file=sys.stderr)
        sys.exit(1)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"index.json JSON 语法错误: {e}", file=sys.stderr)
        sys.exit(1)


def _load_pages(meta_dir):
    """返回 {"pages/<受众>/<章>/<页>": data}（key 不含 .json 后缀，与 update-page 的 --page 兼容）。"""
    meta_dir = Path(meta_dir)
    pages = {}
    pages_dir = meta_dir / "pages"
    if pages_dir.exists():
        for f in sorted(pages_dir.rglob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                pages[f.relative_to(meta_dir).with_suffix("").as_posix()] = data
    return pages


ROLE_ALIASES = {"secondary": "supporting"}  # 2026-07 期间生成的 wiki 用了 secondary


def _source_paths(page_data, role=None):
    """按角色取源码路径。secondary 视为 supporting，否则这些条目在反向映射里会被整个忽略。"""
    out = set()
    for sf in page_data.get("source_files", []) or []:
        if isinstance(sf, dict) and isinstance(sf.get("path"), str):
            sf_role = ROLE_ALIASES.get(sf.get("role"), sf.get("role"))
            if role is None or sf_role == role:
                out.add(sf["path"])
    return out


def _name_status(base, head, repo_root, include_workdir=False):
    """解析 git diff --name-status -M -C。返回 dict。"""
    rng = [base] if include_workdir else [f"{base}..{head}"]
    code, out, err = _git(["diff", "--name-status", "-M50%", "-C50%", "--no-color"] + rng, cwd=repo_root)
    if code != 0:
        print(f"git diff 失败: {err}", file=sys.stderr)
        sys.exit(1)
    added, modified, deleted, renamed, copied = [], [], [], [], []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        if status == "A":
            added.append(parts[1])
        elif status == "M" or status == "T":
            modified.append(parts[1])
        elif status == "D":
            deleted.append(parts[1])
        elif status.startswith("R") and len(parts) >= 3:
            renamed.append({"from": parts[1], "to": parts[2], "similarity": int(status[1:] or 100)})
        elif status.startswith("C") and len(parts) >= 3:
            copied.append({"from": parts[1], "to": parts[2], "similarity": int(status[1:] or 100)})
            added.append(parts[2])
        else:
            modified.append(parts[-1])
    return {"added": added, "modified": modified, "deleted": deleted, "renamed": renamed, "copied": copied}


def _rename_chains(base, head, repo_root, renamed):
    """按 commit 顺序追踪 a→b→c 的 rename 链，为每个 rename 补 chain 字段。"""
    code, out, _ = _git(["log", "--reverse", "--name-status", "-M50%", "--format=%H", f"{base}..{head}"], cwd=repo_root)
    if code != 0:
        return renamed
    latest_of = {}   # 原始路径 → 当前路径
    chain_of = {}    # 当前路径 → [历史路径...]
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[0].startswith("R"):
            src, dst = parts[1], parts[2]
            history = chain_of.pop(src, [src])
            chain_of[dst] = history + [dst]
            for p in history:
                latest_of[p] = dst
    for r in renamed:
        ch = chain_of.get(r["to"])
        if ch and len(ch) > 2:
            r["chain"] = ch
    return renamed


# ─── precheck ────────────────────────────────────────────────────────────────

def cmd_precheck(args):
    index = _load_index(args.meta_dir)
    repo_root, is_git = _repo_root(args.repo_root)
    issues = []
    if not is_git:
        print(json.dumps({"ok": False, "issues": [{"type": "not_a_git_repo", "path": str(repo_root)}]}))
        return
    base = (args.base or index.get("last_synced_commit", "") or "").strip()
    head_code, head, _ = _git(["rev-parse", "HEAD"], cwd=repo_root)
    head = head.strip()

    # 符号引用（HEAD / 分支名 / 短 hash）会让 base..HEAD 恒为空，必须显式拦截
    if base and not re.fullmatch(r"[0-9a-f]{40}", base):
        issue = {"type": "symbolic_base", "commit": base,
                 "detail": "last_synced_commit 不是完整 40 位 hash，diff 结果不可信",
                 "options": ["resolve", "specify", "rebuild"]}
        code, resolved, _ = _git(["rev-parse", "--verify", base + "^{commit}"], cwd=repo_root)
        if code == 0 and resolved.strip() and resolved.strip() != head:
            issue["resolved"] = resolved.strip()
        issues.append(issue)

    code, _, _ = _git(["cat-file", "-e", f"{base}^{{commit}}"], cwd=repo_root)
    reachable = code == 0
    if reachable:
        code, _, _ = _git(["merge-base", "--is-ancestor", base, "HEAD"], cwd=repo_root)
        reachable = code == 0
    if not reachable:
        issue = {"type": "unreachable_commit", "commit": base,
                 "options": ["use_merge_base", "full_rebuild", "specify_start"]}
        code, mb, _ = _git(["merge-base", base, "HEAD"], cwd=repo_root)
        if code == 0 and mb.strip():
            issue["merge_base"] = mb.strip()
        issues.append(issue)

    code, status, _ = _git(["status", "--porcelain"], cwd=repo_root)
    dirty = [l for l in status.splitlines() if l.strip()]
    if dirty:
        issues.append({"type": "dirty_workdir", "count": len(dirty), "files": [l[3:] for l in dirty[:20]],
                       "options": ["include", "exclude"]})

    recorded_branch = index.get("last_synced_branch")
    code, cur, _ = _git(["branch", "--show-current"], cwd=repo_root)
    cur = cur.strip()
    if recorded_branch and cur and recorded_branch != cur:
        issues.append({"type": "branch_mismatch", "recorded": recorded_branch, "current": cur})

    print(json.dumps({"ok": len(issues) == 0, "issues": issues, "base": base, "head": head,
                      "branch": cur or None}, ensure_ascii=False))


# ─── collect ─────────────────────────────────────────────────────────────────

def cmd_collect(args):
    repo_root, is_git = _repo_root(args.repo_root)
    if not is_git:
        print(json.dumps({"ok": False, "issues": [{"type": "not_a_git_repo", "path": str(repo_root)}]}))
        return
    ns = _name_status(args.base, args.head, repo_root, include_workdir=args.include_workdir)
    renamed = _rename_chains(args.base, args.head, repo_root, ns["renamed"])

    # 拆文件候选：同一来源被 rename/copy 到 ≥2 个目标
    targets = defaultdict(list)
    for r in renamed + ns["copied"]:
        targets[r["from"]].append(r["to"])
    split_candidates = [{"from": src, "to": sorted(set(dsts))} for src, dsts in targets.items() if len(set(dsts)) >= 2]

    code, log, _ = _git(["log", "--format=%h %s", f"{args.base}..{args.head}"], cwd=repo_root)
    commits = log.splitlines() if code == 0 else []
    print(json.dumps({
        "ok": True, "base": args.base, "head": args.head,
        "added": ns["added"], "modified": ns["modified"], "deleted": ns["deleted"],
        "renamed": renamed, "split_candidates": split_candidates,
        "commit_count": len(commits), "commits": commits[:50],
    }, ensure_ascii=False))


# ─── affected-pages ──────────────────────────────────────────────────────────

def cmd_affected_pages(args):
    pages = _load_pages(args.meta_dir)
    repo_root, is_git = _repo_root(args.repo_root)
    if not is_git:
        print(json.dumps({"ok": False, "issues": [{"type": "not_a_git_repo", "path": str(repo_root)}]}))
        return
    ns = _name_status(args.base, args.head, repo_root, include_workdir=args.include_workdir)
    changed_files = set(ns["added"]) | set(ns["modified"])
    deleted_files = set(ns["deleted"])
    rename_map = {r["from"]: r["to"] for r in ns["renamed"]}
    changed_files |= set(rename_map.values())

    primary_pages, supporting_pages, deprecated_pages, renamed_sources = [], [], [], []
    needs_review, reasons = [], {}
    for page_rel, page_data in pages.items():
        primary_paths = _source_paths(page_data, "primary")
        supporting_paths = _source_paths(page_data, "supporting")
        for old, new in rename_map.items():
            if old in primary_paths or old in supporting_paths:
                renamed_sources.append({"page": page_rel, "from": old, "to": new})
        # 被 rename 的源码按「已变更」处理，而不是「已删除」
        primary_eff = {rename_map.get(p, p) for p in primary_paths}
        supporting_eff = {rename_map.get(p, p) for p in supporting_paths}

        hit_primary = sorted(primary_eff & changed_files)
        hit_supporting = sorted(supporting_eff & changed_files)
        gone_primary = sorted(primary_eff & deleted_files)

        if not primary_eff and not supporting_eff:
            # 没有任何源码锚点：既不会被判为受影响，也不会被判为废弃，属于要人看一眼的情况
            needs_review.append(page_rel)
            reasons[page_rel] = [{"reason": "no_source_files"}]
        elif primary_eff and primary_eff.issubset(deleted_files) and not hit_primary:
            deprecated_pages.append(page_rel)
            reasons[page_rel] = [{"path": p, "role": "primary", "status": "deleted"} for p in gone_primary]
        elif hit_primary:
            primary_pages.append(page_rel)
            reasons[page_rel] = [{"path": p, "role": "primary", "status": "changed"} for p in hit_primary]
        elif hit_supporting:
            supporting_pages.append(page_rel)
            reasons[page_rel] = [{"path": p, "role": "supporting", "status": "changed"} for p in hit_supporting]
        elif gone_primary:
            # 部分 primary 被删、其余未变：既不是重写候选也不是废弃，会从三个桶里漏掉
            needs_review.append(page_rel)
            reasons[page_rel] = [{"path": p, "role": "primary", "status": "deleted"} for p in gone_primary]

    total = len(primary_pages) + len(supporting_pages) + len(deprecated_pages) + len(needs_review)
    limit = None if args.no_truncate else TRUNCATE_LIMIT
    result = {
        "primary": primary_pages[:limit], "supporting": supporting_pages[:limit],
        "deprecated": deprecated_pages[:limit],
        "needs_review": needs_review[:limit],
        "counts": {"primary": len(primary_pages), "supporting": len(supporting_pages),
                   "deprecated": len(deprecated_pages), "needs_review": len(needs_review)},
        "reasons": reasons,
    }
    if renamed_sources:
        result["renamed_sources"] = renamed_sources
    if limit is not None and total > limit:
        result["truncated"] = True
        result["total"] = total
    print(json.dumps(result, ensure_ascii=False))


# ─── orphan-scan ─────────────────────────────────────────────────────────────

def _glob_to_regex(pat):
    """支持 ** 跨目录的 glob → 正则。"""
    i, n, out = 0, len(pat), []
    while i < n:
        c = pat[i]
        if c == "*":
            if pat[i:i + 3] == "**/":
                out.append("(?:.*/)?"); i += 3; continue
            if pat[i:i + 2] == "**":
                out.append(".*"); i += 2; continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def _is_ignored(path, regexes):
    name = path.rsplit("/", 1)[-1]
    return any(r.match(path) or r.match(name) for r in regexes)


def _default_ignore_for(primary_type):
    key = (primary_type or "").lower()
    for lang, pats in DEFAULT_IGNORE.items():
        if lang in key:
            return list(pats)
    if "monorepo" in key:
        return list(DEFAULT_IGNORE["typescript"]) + list(DEFAULT_IGNORE["python"])
    return []


def cmd_orphan_scan(args):
    index = _load_index(args.meta_dir)
    pages = _load_pages(args.meta_dir)
    repo_root, is_git = _repo_root(args.repo_root)
    if not is_git:
        print(json.dumps({"ok": False, "issues": [{"type": "not_a_git_repo", "path": str(repo_root)}]}))
        return

    if args.ignore_patterns:
        raw = args.ignore_patterns.strip()
        patterns = json.loads(raw) if raw.startswith("[") else [p.strip() for p in raw.split(",") if p.strip()]
    elif index.get("ignore_patterns"):
        patterns = list(index["ignore_patterns"])
    else:
        patterns = _default_ignore_for(index.get("primary_type"))
    patterns = patterns + [p for p in COMMON_IGNORE if p not in patterns]
    # wiki 自身与元数据永远排除
    wiki_root = (index.get("wiki_root") or "").strip()
    if wiki_root.startswith("./"):
        wiki_root = wiki_root[2:]
    wiki_root = wiki_root.strip("/")
    if wiki_root and wiki_root != ".":
        patterns.append(wiki_root + "/**")
    patterns += [".wiki-meta/**", "**/.wiki-meta/**", ".followup*.md"]
    regexes = [_glob_to_regex(p) for p in patterns]

    recorded = set()
    for data in pages.values():
        recorded |= _source_paths(data)
        for a in data.get("anchor_material", []) or []:
            if isinstance(a, str):
                recorded.add(a)

    code, out, _ = _git(["ls-files", "--cached", "--others", "--exclude-standard"], cwd=repo_root)
    files = [f for f in out.splitlines() if f.strip()]

    # --since：只保留自该 commit 起新增的文件，用于回答「新出现哪些未覆盖模块」
    since_added = None
    since = args.since or args.base
    if since:
        ns = _name_status(since, "HEAD", repo_root)
        since_added = set(ns["added"]) | {r["to"] for r in ns["renamed"]} | {c["to"] for c in ns["copied"]}
        files = [f for f in files if f in since_added]
    orphans = []
    for f in files:
        if f in recorded or _is_ignored(f, regexes):
            continue
        d = f.rsplit("/", 1)[0] + "/" if "/" in f else "./"
        orphans.append({"path": f, "dir": d})

    by_dir = defaultdict(list)
    for o in orphans:
        by_dir[o["dir"]].append(o["path"])
    clusters = [{"dir": d, "count": len(fs), "files": fs[:20]}
                for d, fs in sorted(by_dir.items(), key=lambda kv: -len(kv[1])) if len(fs) >= CLUSTER_MIN]

    limit = None if args.no_truncate else ORPHAN_LIMIT
    result = {"orphans": orphans[:limit], "orphans_total": len(orphans), "clusters": clusters,
              "ignore_patterns_used": patterns, "recorded_files": len(recorded), "scanned_files": len(files)}
    if since_added is not None:
        result["since"] = since
        result["added_since_base"] = len(since_added)
    if limit is not None and len(orphans) > limit:
        result["truncated"] = True
    print(json.dumps(result, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Phase Δ git 操作工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("precheck", help="commit 可达性 / 工作区 / 分支一致性预检")
    p.add_argument("--meta-dir", required=True)
    p.add_argument("--repo-root")
    p.add_argument("--base", help="覆盖 index.json 的 last_synced_commit（纠正基线后复检用）")

    p = sub.add_parser("collect", help="收集 base..head 的差异（含 rename 链与拆文件候选）")
    p.add_argument("--base", required=True)
    p.add_argument("--head", default="HEAD")
    p.add_argument("--repo-root")
    p.add_argument("--include-workdir", action="store_true", help="把未提交的工作区改动一并纳入")

    p = sub.add_parser("affected-pages", help="把差异反向映射到受影响的 wiki 页")
    p.add_argument("--meta-dir", required=True)
    p.add_argument("--base", required=True)
    p.add_argument("--head", default="HEAD")
    p.add_argument("--repo-root")
    p.add_argument("--include-workdir", action="store_true")
    p.add_argument("--no-truncate", action="store_true", help="不截断到 %d 条" % TRUNCATE_LIMIT)

    p = sub.add_parser("orphan-scan", help="扫描未被任何页面记录的源码文件")
    p.add_argument("--meta-dir", required=True)
    p.add_argument("--repo-root", required=True)
    p.add_argument("--since", help="只报自该 commit 起新增且未被记录的文件（回答「新出现哪些未覆盖模块」）")
    p.add_argument("--base", help="--since 的等价别名，与其他子命令的 --base 保持同名")
    p.add_argument("--no-truncate", action="store_true", help="不截断到 %d 条" % ORPHAN_LIMIT)
    p.add_argument("--ignore-patterns", help='JSON 数组或逗号分隔的 glob；缺省用 schema 的 ignore_patterns')

    args = parser.parse_args()
    {"precheck": cmd_precheck, "collect": cmd_collect,
     "affected-pages": cmd_affected_pages, "orphan-scan": cmd_orphan_scan}[args.cmd](args)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""计算 git diff 影响的 wiki 页清单（人类可读版；机器可读请用 delta-git.py affected-pages）。

用法：python3 diff-impact.py --meta-dir <path> --base <commit> [--head HEAD] [--repo-root <path>]
"""
import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def _load_delta_git():
    spec = importlib.util.spec_from_file_location("delta_git", Path(__file__).with_name("delta-git.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    parser = argparse.ArgumentParser(description="计算 git diff 影响的 wiki 页清单")
    parser.add_argument("--meta-dir", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--repo-root")
    args = parser.parse_args()

    cmd = [sys.executable, str(Path(__file__).with_name("delta-git.py")), "affected-pages",
           "--meta-dir", args.meta_dir, "--base", args.base, "--head", args.head, "--no-truncate"]
    if args.repo_root:
        cmd += ["--repo-root", args.repo_root]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        sys.exit(1)
    d = json.loads(r.stdout)
    if not d.get("primary") and not d.get("supporting") and not d.get("deprecated"):
        print(f"{args.base}..{args.head}：没有页面受影响")
        return
    for group, label in (("primary", "A 组 primary 命中（默认重写）"),
                         ("supporting", "B 组 仅 supporting 命中（仅提示）"),
                         ("deprecated", "D 组 primary 源码全部删除（候选 deprecated）")):
        items = d.get(group, [])
        print(f"\n{label}：{len(items)} 页")
        for p in items:
            print(f"  - {p[len('pages/'):] if p.startswith('pages/') else p}")
    if d.get("renamed_sources"):
        print("\n源码被重命名的页（需更新 source_files）：")
        for r_ in d["renamed_sources"]:
            print(f"  - {r_['page']}: {r_['from']} → {r_['to']}")


if __name__ == "__main__":
    main()

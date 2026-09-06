#!/usr/bin/env python3
"""检查 skill 内容 hash 是否与 CHANGELOG 记录一致（检测「改了 SKILL.md 却没走 --upgrade」）。

用法：python3 skill-self-check.py --skill-root <path> [--print-hash] [--strict]

hash 定义（content-hash protocol v1）：
  sha256( 依次拼接 "<相对路径>\\n<文件内容>\\n" ) 的前 16 位十六进制，
  文件范围 = SKILL.md + references/** + scripts/**（按路径排序），
  其中形如 <!-- skill-content-hash: ... --> 的行在计算前剔除。
CHANGELOG.md 顶部须有 <!-- skill-content-hash: <16hex> -->。
退出码：默认始终 0（不阻断 wiki 生成）；--strict 时漂移返回 1；脚本错误返回 2。
"""
import argparse
import hashlib
import re
import sys
from pathlib import Path

HASH_LINE = re.compile(r"^\s*<!--\s*skill-content-hash:.*?-->\s*$", re.M)
VERSION_RE = re.compile(r"<!--\s*skill-version:\s*([0-9A-Za-z.\-]+)\s*-->")
CHANGELOG_HASH_RE = re.compile(r"<!--\s*skill-content-hash:\s*([0-9a-f]{16})\s*-->")
CHANGELOG_VER_RE = re.compile(r"^##\s*\[([0-9A-Za-z.\-]+)\]", re.M)


def hashed_files(skill_root):
    files = [skill_root / "SKILL.md"]
    for sub in ("references", "scripts"):
        d = skill_root / sub
        if d.is_dir():
            files += [p for p in sorted(d.rglob("*")) if p.is_file() and "__pycache__" not in p.parts]
    return files


def compute_hash(skill_root):
    h = hashlib.sha256()
    for p in hashed_files(skill_root):
        rel = p.relative_to(skill_root).as_posix()
        text = p.read_text(encoding="utf-8", errors="replace")
        text = HASH_LINE.sub("", text)
        h.update(f"{rel}\n{text}\n".encode("utf-8"))
    return h.hexdigest()[:16]


def main():
    parser = argparse.ArgumentParser(description="检查 skill 内容 hash 与 CHANGELOG 是否一致")
    parser.add_argument("--skill-root", required=True)
    parser.add_argument("--print-hash", action="store_true", help="只输出当前 hash")
    parser.add_argument("--strict", action="store_true", help="漂移时以退出码 1 结束")
    args = parser.parse_args()

    root = Path(args.skill_root).resolve()
    if not (root / "SKILL.md").exists():
        print(f"SKILL.md 不存在: {root}", file=sys.stderr)
        sys.exit(2)
    current = compute_hash(root)
    if args.print_hash:
        print(current)
        return

    drift = []
    changelog = root / "CHANGELOG.md"
    if not changelog.exists():
        drift.append("CHANGELOG.md 不存在")
        recorded = None
    else:
        text = changelog.read_text(encoding="utf-8")
        m = CHANGELOG_HASH_RE.search(text)
        recorded = m.group(1) if m else None
        if recorded is None:
            drift.append("CHANGELOG.md 顶部缺少 <!-- skill-content-hash: ... -->")
        elif recorded != current:
            drift.append(f"内容 hash {current} ≠ CHANGELOG 记录 {recorded}")
        vm = VERSION_RE.search((root / "SKILL.md").read_text(encoding="utf-8"))
        cm = CHANGELOG_VER_RE.search(text)
        if vm and cm and vm.group(1) != cm.group(1):
            drift.append(f"SKILL.md 版本 {vm.group(1)} ≠ CHANGELOG 最新条目 {cm.group(1)}")

    if drift:
        print("⚠️ skill 内容已变更但 CHANGELOG 未更新：" + "；".join(drift))
        print("   修复：/repo-wiki --upgrade --recover（或 scripts/release-finalize.sh --recover）")
        if args.strict:
            sys.exit(1)
    else:
        print(f"✓ skill 内容 hash 一致（{current}）")


if __name__ == "__main__":
    main()

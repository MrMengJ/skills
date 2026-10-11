#!/usr/bin/env python3
"""检查 SKILL.md 的版本号是否与 CHANGELOG 最新条目一致（检测「手改了版本号却没走 --upgrade」）。

用法：python3 skill-self-check.py --skill-root <path> [--strict]

退出码：默认始终 0（不阻断 wiki 生成）；--strict 时不一致返回 1；脚本错误返回 2。
"""
import argparse
import re
import sys
from pathlib import Path

VERSION_RE = re.compile(r"<!--\s*skill-version:\s*([0-9A-Za-z.\-]+)\s*-->")
CHANGELOG_VER_RE = re.compile(r"^##\s*\[([0-9A-Za-z.\-]+)\]", re.M)


def main():
    parser = argparse.ArgumentParser(description="检查 SKILL.md 版本号与 CHANGELOG 是否一致")
    parser.add_argument("--skill-root", required=True)
    parser.add_argument("--strict", action="store_true", help="不一致时以退出码 1 结束")
    args = parser.parse_args()

    root = Path(args.skill_root).resolve()
    if not (root / "SKILL.md").exists():
        print(f"SKILL.md 不存在: {root}", file=sys.stderr)
        sys.exit(2)

    drift = []
    vm = VERSION_RE.search((root / "SKILL.md").read_text(encoding="utf-8"))
    changelog = root / "CHANGELOG.md"
    if not changelog.exists():
        drift.append("CHANGELOG.md 不存在")
    else:
        cm = CHANGELOG_VER_RE.search(changelog.read_text(encoding="utf-8"))
        if vm and cm and vm.group(1) != cm.group(1):
            drift.append(f"SKILL.md 版本 {vm.group(1)} ≠ CHANGELOG 最新条目 {cm.group(1)}")

    if drift:
        print("⚠️ SKILL.md 版本号与 CHANGELOG 不一致：" + "；".join(drift))
        print("   修复：把两处版本号改成一致；发新版本走 /repo-wiki --upgrade")
        if args.strict:
            sys.exit(1)
    else:
        print("✓ SKILL.md 版本号与 CHANGELOG 一致" + (f"（{vm.group(1)}）" if vm else ""))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""校验 design-notes/ 目录结构。

用法：python3 design-notes-lint.py --skill-root <path>

规则：
  1. design-notes/INDEX.md 必须存在
  2. 每个 design-notes/v<semver>-<slug>.md 必须在 INDEX.md 中被引用；INDEX.md 引用的文件必须存在
  3. 文件名须匹配 v<主>.<次>.<补>-<slug>.md
  4. 每份 note 必须含四个固定小节：改造背景 / 改造目标 / 用户文档影响分析 / 改造主体步骤
退出码：0 通过；1 有错误。
"""
import argparse
import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^v\d+\.\d+\.\d+-[A-Za-z0-9][A-Za-z0-9_\-]*\.md$")
REQUIRED_SECTIONS = ["改造背景", "改造目标", "用户文档影响分析", "改造主体步骤"]


def main():
    parser = argparse.ArgumentParser(description="校验 design-notes/ 目录结构")
    parser.add_argument("--skill-root", required=True)
    args = parser.parse_args()
    root = Path(args.skill_root).resolve()
    notes_dir = root / "design-notes"
    errors, warnings = [], []

    if not notes_dir.is_dir():
        print(f"✗ design-notes/ 目录不存在: {notes_dir}")
        sys.exit(1)
    index = notes_dir / "INDEX.md"
    if not index.exists():
        errors.append("design-notes/INDEX.md 不存在")
        index_text = ""
    else:
        index_text = index.read_text(encoding="utf-8")

    notes = sorted(p for p in notes_dir.glob("*.md") if p.name != "INDEX.md")
    for p in notes:
        if not NAME_RE.match(p.name):
            errors.append(f"{p.name}: 文件名须为 v<semver>-<slug>.md")
        if p.name not in index_text:
            errors.append(f"{p.name}: 未在 INDEX.md 中登记")
        text = p.read_text(encoding="utf-8")
        for sec in REQUIRED_SECTIONS:
            if not re.search(r"^#{1,3}\s*" + re.escape(sec), text, re.M):
                errors.append(f"{p.name}: 缺少小节「{sec}」")
    for ref in re.findall(r"\(([^)]+\.md)\)", index_text):
        if not (notes_dir / ref).exists():
            errors.append(f"INDEX.md 引用的 {ref} 不存在")

    if not notes:
        warnings.append("design-notes/ 下没有任何 note")
    for w in warnings:
        print(f"  ⚠️ {w}")
    for e in errors:
        print(f"  ✗ {e}")
    if errors:
        print(f"✗ design-notes 校验失败：{len(errors)} 个问题")
        sys.exit(1)
    print(f"✓ design-notes 校验通过（{len(notes)} 份 note）")


if __name__ == "__main__":
    main()

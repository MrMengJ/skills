#!/usr/bin/env python3
"""展示本次升级可能影响的用户文档清单，辅助「收尾第 7 步：用户文档审查」。

用法：python3 docs-drift-helper.py --skill-root <path> [--plan <path>] [--followup "<待办文本>"]

行为：
  - 列出 README.md / docs/usage.md / docs/maintainers.md 的存在性、最后修改时间，
    并与 SKILL.md / references / scripts 的最新修改时间比较，标出「疑似落后」的文档
  - 给定 --plan 时，解析 plan 的「用户文档影响分析」小节，把其中提到的文档标记为「计划中要求更新」
  - 给定 --followup 时，把待办追加到 .upgrade/docs-followup.md（对应三选一中的「写入 followup」）
退出码：始终 0（结论由维护者三选一：已无需更新 / 已更新 / 写入 followup）。
"""
import argparse
import datetime as _dt
import re
from pathlib import Path

USER_DOCS = ["README.md", "docs/usage.md", "docs/maintainers.md"]


def latest_mtime(paths):
    ts = [p.stat().st_mtime for p in paths if p.exists()]
    return max(ts) if ts else 0


def fmt(ts):
    return _dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "—"


def plan_mentions(plan_path):
    if not plan_path or not Path(plan_path).exists():
        return set()
    text = Path(plan_path).read_text(encoding="utf-8")
    m = re.search(r"^#{1,3}\s*用户文档影响分析.*?(?=^#{1,3}\s|\Z)", text, re.M | re.S)
    section = m.group(0) if m else text
    return {d for d in USER_DOCS if d in section or Path(d).name in section}


def main():
    parser = argparse.ArgumentParser(description="展示升级影响的用户文档清单")
    parser.add_argument("--skill-root", required=True)
    parser.add_argument("--plan", help="升级 plan 文件路径")
    parser.add_argument("--followup", help="把该待办写入 .upgrade/docs-followup.md")
    args = parser.parse_args()
    root = Path(args.skill_root).resolve()

    sources = [root / "SKILL.md"] + [p for sub in ("references", "scripts") for p in (root / sub).rglob("*") if p.is_file()]
    src_latest = latest_mtime(sources)
    mentioned = plan_mentions(args.plan)

    print(f"skill 内容最后修改：{fmt(src_latest)}")
    print("用户文档状态：")
    for doc in USER_DOCS:
        p = root / doc
        if not p.exists():
            status = "✗ 不存在"
        elif p.stat().st_mtime < src_latest:
            status = f"⚠️ 疑似落后（{fmt(p.stat().st_mtime)}）"
        else:
            status = f"✓ 较新（{fmt(p.stat().st_mtime)}）"
        flag = "  ← plan 要求更新" if doc in mentioned else ""
        print(f"  {doc:<22} {status}{flag}")

    if args.followup:
        up = root / ".upgrade"
        up.mkdir(exist_ok=True)
        f = up / "docs-followup.md"
        stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        with f.open("a", encoding="utf-8") as fh:
            if f.stat().st_size == 0:
                fh.write("# 用户文档待办\n\n")
            fh.write(f"- [ ] {stamp} {args.followup}\n")
        print(f"已写入 {f}")

    print("\n请三选一：(a) 已无需更新  (b) 已更新  (c) 写入 .upgrade/docs-followup.md（--followup \"...\"）")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""--upgrade 的纯 CLI 入口（Level 3：无 agent / 无 plan 模式的环境）。

用法：
  python3 upgrade-cli.py --interactive [--skill-root <path>]
  python3 upgrade-cli.py --no-prompt --from-json <plan.json> [--skill-root <path>]

流程：按「升级 Plan 模板」逐项收集 4 节内容（改造背景 / 改造目标 / 用户文档影响分析 / 改造主体步骤），
写出 {{SKILL_ROOT}}/.upgrade/pending-plan-<TIMESTAMP>.md，然后提示用 release-finalize.sh 执行收尾固定段。
本脚本不修改 SKILL.md 本身：改造主体由维护者按 plan 手工/借助 agent 完成。
"""
import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path

SECTIONS = [
    ("background", "改造背景", "问题 / 需求描述（多行，空行结束）"),
    ("goal", "改造目标", "完成后有什么不同（多行，空行结束）"),
    ("docs_impact", "用户文档影响分析", "逐条回答：是否影响 README.md？docs/usage.md？docs/maintainers.md？（多行，空行结束）"),
    ("steps", "改造主体步骤", "含文档同步步骤（多行，空行结束）"),
]
CLOSING = """## 收尾（固定段，禁止修改）
1. 拷贝 plan 文件到 design-notes/v{{NEW_VERSION}}-{{TOPIC_SLUG}}.md
2. 更新 design-notes/INDEX.md
3. 更新 SKILL.md 顶部 <!-- skill-version: {{NEW_VERSION}} -->
4. 重算 content-hash，更新 CHANGELOG.md 顶部 <!-- skill-content-hash: ... -->
5. 在 CHANGELOG.md 写新版本条目
6. 运行 scripts/design-notes-lint.py + scripts/skill-self-check.py
7. 用户文档审查（scripts/docs-drift-helper.py），三选一：已无需更新 / 已更新 / 写入 .upgrade/docs-followup.md
8. （可选）git add -A && git commit -m "chore(skill): upgrade to v{{NEW_VERSION}} — {{TOPIC_SLUG}}"
"""


def read_multiline(prompt):
    print(f"\n{prompt}")
    lines = []
    while True:
        try:
            line = input("> ")
        except EOFError:
            break
        if line.strip() == "" and lines:
            break
        if line.strip() == "" and not lines:
            continue
        lines.append(line)
    return "\n".join(lines)


def current_version(skill_root):
    m = re.search(r"<!--\s*skill-version:\s*([0-9A-Za-z.\-]+)\s*-->", (skill_root / "SKILL.md").read_text(encoding="utf-8"))
    return m.group(1) if m else "unknown"


def render(plan, new_version, slug):
    body = [f"# 升级 Plan：v{new_version} — {slug}", "",
            f"生成时间：{_dt.datetime.now():%Y-%m-%d %H:%M}", ""]
    for key, title, _ in SECTIONS:
        body += [f"## {title}", plan.get(key, "").strip() or "（未填写）", ""]
    body.append(CLOSING.replace("{{NEW_VERSION}}", new_version).replace("{{TOPIC_SLUG}}", slug))
    return "\n".join(body)


def main():
    parser = argparse.ArgumentParser(description="--upgrade 的纯 CLI 入口")
    parser.add_argument("--skill-root")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--interactive", action="store_true", help="通过 stdin 逐项提问")
    mode.add_argument("--no-prompt", action="store_true", help="不提问，从 --from-json 读取")
    parser.add_argument("--from-json", help='JSON：{"new_version","topic_slug","background","goal","docs_impact","steps"}')
    parser.add_argument("--new-version")
    parser.add_argument("--topic-slug")
    args = parser.parse_args()

    root = Path(args.skill_root).resolve() if args.skill_root else Path(__file__).resolve().parent.parent
    if not (root / "SKILL.md").exists():
        print(f"SKILL.md 不存在: {root}", file=sys.stderr)
        sys.exit(1)
    cur = current_version(root)

    plan = {}
    if args.no_prompt:
        if not args.from_json:
            print("--no-prompt 需要 --from-json", file=sys.stderr)
            sys.exit(1)
        plan = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        new_version = args.new_version or plan.get("new_version")
        slug = args.topic_slug or plan.get("topic_slug")
    else:
        print(f"🪄 repo-wiki --upgrade（CLI 模式）当前版本 v{cur}")
        new_version = args.new_version or input(f"新版本号（当前 {cur}）> ").strip()
        slug = args.topic_slug or input("主题 slug（英文小写连字符，如 add-go-support）> ").strip()
        for key, title, hint in SECTIONS:
            plan[key] = read_multiline(f"## {title} — {hint}")

    if not new_version or not slug:
        print("缺少 new_version / topic_slug", file=sys.stderr)
        sys.exit(1)
    if not re.match(r"^[a-z0-9][a-z0-9\-]*$", slug):
        print(f"topic_slug 只能含小写字母、数字、连字符: {slug}", file=sys.stderr)
        sys.exit(1)

    up = root / ".upgrade"
    up.mkdir(exist_ok=True)
    out = up / f"pending-plan-{_dt.datetime.now():%Y%m%d-%H%M%S}.md"
    out.write_text(render(plan, new_version, slug), encoding="utf-8")
    print(f"\n✓ plan 已写入 {out}")
    print("下一步：按 plan 完成改造主体，然后执行收尾固定段：")
    print(f"  {root / 'scripts' / 'release-finalize.sh'} --plan {out} --new-version {new_version} --topic-slug {slug}")


if __name__ == "__main__":
    main()

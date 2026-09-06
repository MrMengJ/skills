#!/usr/bin/env python3
"""显示 /repo-wiki 用法（版本号从 SKILL.md 动态读取）。

用法：python3 help.py [--skill-root <path>]

若 docs/usage.md 中存在 <!-- HELP-PARAM-START --> … <!-- HELP-PARAM-END --> 区块，
参数表以该区块为准（单一可信源）；否则打印内置表。
"""
import argparse
import re
import sys
from pathlib import Path

BUILTIN_PARAMS = """\
| 参数 | 作用 |
|---|---|
| （无参数） | 首次生成：Phase 0 调研 → D1–D5 决策点 → 分轮生成 → 验证；已有 .wiki-meta 时询问增量/重建 |
| --update | Phase Δ 增量更新：按 git diff 反向映射受影响页并重写 |
| --rebuild | 备份现有 wiki 后全量重建 |
| --dry-run | 只展示差异与受影响页，不写任何文件 |
| --from <commit> | 覆盖 last_synced_commit 作为增量起点（早于上次同步时会警告） |
| --platform=tier1/2/3 | 强制指定交互层级（结构化工具 / 文本 / 纯 CLI） |
| --upgrade | 升级 skill 自身（plan 模式 / 对话 / CLI 三档） |
| --upgrade --recover | 只补 hash / CHANGELOG / design-notes 元数据，不走 plan |
| --help, -h | 显示本帮助 |"""


def skill_root_from(arg):
    return Path(arg).resolve() if arg else Path(__file__).resolve().parent.parent


def read_version(skill_root):
    skill_md = skill_root / "SKILL.md"
    if not skill_md.exists():
        raise FileNotFoundError(f"SKILL.md 不存在: {skill_md}")
    m = re.search(r"<!--\s*skill-version:\s*([0-9A-Za-z.\-]+)\s*-->", skill_md.read_text(encoding="utf-8"))
    if not m:
        raise ValueError("SKILL.md 中未找到 <!-- skill-version: X -->")
    return m.group(1)


def read_param_table(skill_root):
    usage = skill_root / "docs" / "usage.md"
    if not usage.exists():
        return None
    m = re.search(r"<!--\s*HELP-PARAM-START\s*-->\n(.*?)<!--\s*HELP-PARAM-END\s*-->", usage.read_text(encoding="utf-8"), re.S)
    return m.group(1).strip() if m else None


def main():
    parser = argparse.ArgumentParser(description="显示 repo-wiki 用法")
    parser.add_argument("--skill-root")
    args = parser.parse_args()
    try:
        root = skill_root_from(args.skill_root)
        version = read_version(root)
    except Exception as e:  # help.py 失败时调度器展示 stderr 并退出
        print(f"help.py 错误：{e}", file=sys.stderr)
        sys.exit(1)
    params = read_param_table(root) or BUILTIN_PARAMS
    print(f"""🪄 /repo-wiki v{version} — 为任意代码项目生成结构化 wiki

用法：/repo-wiki [--update | --rebuild | --dry-run] [--from <commit>] [--platform=tierN]
      /repo-wiki --upgrade [--recover]
      /repo-wiki --help

{params}

交互元命令（任何决策点均可输入）：? 查看说明 | back 回上步 | skip-all 全部默认 | edit-schema 直接改 .wiki-meta | cancel 取消

文档：README.md（快速开始）· docs/usage.md（决策点 / Phase Δ / 故障排查）· docs/maintainers.md（升级流程）
skill 根目录：{root}""")


if __name__ == "__main__":
    main()

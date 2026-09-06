<!-- template-version: 2 -->
<!-- 重建说明：原件于 2026-09-03 丢失，本文按 SKILL.md「SKILL_ROOT 解析协议」节与已生成 wiki 的 runtime.json 实例重写（2026-09-04）。 -->
# SKILL_ROOT 解析协议（v1）

`{{SKILL_ROOT}}` 是 skill 根目录路径占位符。SKILL.md 中所有 `$SKILL_ROOT/scripts/...`、`$SKILL_ROOT/references/...` 都以它为基准。调度器启动时按 5 级 fallback 解析一次，成功后写入 `{{WIKI_ROOT}}/.wiki-meta/runtime.json`，下次启动直接命中缓存。

## 5 级 fallback

| Level | 来源 | 何时命中 | 校验 |
|---|---|---|---|
| 1 | 环境变量 `REPO_WIKI_SKILL_ROOT` | 用户显式导出 | 目录下存在 `SKILL.md` |
| 2 | `{{WIKI_ROOT}}/.wiki-meta/runtime.json` 的 `skill_root` | wiki 已生成过 | 目录仍存在且含 `SKILL.md`；`skill_version` 与当前 SKILL.md 版本不同时**仍可用**，但要在开场卡片提示版本变化 |
| 3 | 常见安装路径探测 | 全局安装 | 依次尝试：`~/.agents/skills/repo-wiki/`、`~/.claude/skills/repo-wiki/`、`<项目>/.claude/skills/repo-wiki/`、`$(npm root -g)/repo-wiki/`、`$(brew --prefix)/share/repo-wiki/` |
| 4 | 调度器自检 | skill 正文被平台注入时 | 平台通常在正文末尾附带 `Base directory for this skill: <path>`；取 `realpath(dirname(SKILL.md))` |
| 5 | 全部失败 | — | 报错并退出：`请 export REPO_WIKI_SKILL_ROOT=/path/to/repo-wiki 后重试`，**不进入任何 Phase** |

解析到的路径一律 `realpath` 化（`~/.claude/skills/repo-wiki` 通常是指向 `~/.agents/skills/repo-wiki` 的软链接，两者等价）。

## runtime.json 字段

```json
{
  "skill_root": "/Users/<me>/.claude/skills/repo-wiki",
  "skill_version": "2.1.0",
  "platform_capabilities": {
    "has_structured_input_tool": true
  },
  "resolved_at": "2026-08-05T00:00:00+08:00",
  "last_round": 7,
  "rounds_total": 7,
  "generation_complete": true
}
```

| 字段 | 写入时机 | 说明 |
|---|---|---|
| `skill_root` | 解析成功后 | Level 1–4 任一命中即写 |
| `skill_version` | 同上 | 取自 SKILL.md `<!-- skill-version: X -->` |
| `platform_capabilities.has_structured_input_tool` | Phase 0 能力探测后 | 见 SKILL.md「交互执行规范」；`--platform=tierN` 强制覆盖时不改写缓存 |
| `resolved_at` | 解析成功后 | ISO 8601 |
| `last_round` / `rounds_total` / `generation_complete` | 每轮结束 | 首次生成的断点续跑信息；`generation_complete=false` 时开场卡片提示「上次生成到第 N/M 轮，是否续跑」 |

## 约束

- `runtime.json` 是**运行时缓存**，必须 git-ignored（首次生成收尾时检查 `.gitignore`，缺失则追加 `{{WIKI_ROOT}}/.wiki-meta/runtime.json`）。`index.json` 与 `pages/` 则要提交。
- 缓存只加速，不代替校验：命中 Level 2 后仍要确认 `SKILL.md` 存在，失效则继续往下走。
- 多 wiki 工作区（同一仓库多个 `.wiki/`）各自持有 runtime.json，互不共享。
- 脚本自身不依赖本协议：所有 `scripts/*.py` 都用 `--meta-dir` / `--wiki-root` / `--skill-root` 显式传路径，`help.py` 与 `upgrade-cli.py` 缺省时取 `dirname(__file__)/..`。

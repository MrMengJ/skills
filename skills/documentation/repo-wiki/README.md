# repo-wiki

为任意代码项目生成**既有广度又有深度**的结构化 wiki 的 agent skill。支持 4 类受众（维护者 / 使用者 / 新人 / 业务方）、多种项目形态（前端库 / 后端服务 / CLI / SDK / 单体业务 / 多语言 monorepo / 微服务集群 / fork 项目），并能按 git diff 增量更新。

> 当前版本见 `SKILL.md` 顶部 `<!-- skill-version -->`；`python3 scripts/help.py` 可随时打印用法。
> 本目录中标注「重建说明」的文件为 2026-09-04 事故恢复后重写，其余为原件（详见 `CHANGELOG.md` 末尾的恢复记录）。

## 快速开始

```
cd <你的项目>
/repo-wiki                 # 首次生成：调研 → 5 个决策点 → 分轮生成 → 验证
/repo-wiki --update        # 源码变动后增量更新
/repo-wiki --dry-run       # 只看会改哪些页
```

首次运行会打印开场卡片并静默调研项目，然后依次问 D1 受众、D2 语言、D3 章节草稿、D4 输出目录、D5 图表；第一轮生成结束后追问 C1 暂停偏好。任何决策点都可输入 `?` / `back` / `skip-all` / `edit-schema` / `cancel`。

## 命令表

| 命令 | 作用 |
|---|---|
| `/repo-wiki` | 首次生成；若已存在 `.wiki-meta/` 则询问增量 / 重建 / 查看状态 |
| `/repo-wiki --update` | Phase Δ 增量更新（schema 校验 → git 预检 → 差异 → 反向映射 → 冲突检测 → 重写 → 孤儿扫描 → 收尾） |
| `/repo-wiki --rebuild` | 备份为 `<wiki>.bak-<TIMESTAMP>/` 后全量重建 |
| `/repo-wiki --dry-run` | 只展示差异与受影响页，不写文件 |
| `/repo-wiki --from <commit>` | 覆盖增量起点（早于上次同步时会警告并默认 dry-run） |
| `/repo-wiki --platform=tier1/2/3` | 强制交互层级 |
| `/repo-wiki --upgrade` | 升级 skill 自身（plan 模式 / 对话 / CLI 三档） |
| `/repo-wiki --upgrade --recover` | 手改 SKILL.md 后只补 hash / CHANGELOG / design-notes |
| `/repo-wiki --help` | 打印 `scripts/help.py` 的帮助 |

## 平台支持

| 平台 | 交互层级 | 说明 |
|---|---|---|
| Claude Code（CLI / IDE / web） | Tier 1 | 决策点用 `AskUserQuestion` 结构化呈现；`--upgrade` 走 plan 模式 |
| opencode / Cursor / Cline / Continue / Aider / Codex CLI / Gemini CLI | Tier 2 | 文本 prompt + 字母选项；`--upgrade` 走对话收集 |
| 无 agent 的纯 CLI | Tier 3 | `scripts/upgrade-cli.py`；wiki 生成本身仍需 agent |

运行环境：Python ≥ 3.8，脚本仅用标准库；需要 `git`。

## 输出结构

```
{{WIKI_ROOT}}/                      ← D4 选定（默认 ./wiki/，常用 ./.wiki/）
├── INDEX.md                        ← 全局索引（末尾含 <!-- repo-wiki-managed --> marker）
├── HOW-TO-UPDATE.md
├── .wiki-meta/
│   ├── index.json                  ← 顶层元信息（提交）
│   ├── pages/<受众>/<NN-章>/<NN-页>.json  ← 每页源码依赖与 sha256（提交）
│   └── runtime.json                ← 运行时缓存（git-ignored）
├── 维护者指南/01-项目全景/01-….md    ← 三层结构：受众 / NN-章节 / NN-页面
└── 使用者指南/01-…/
```

## 目录说明

| 路径 | 内容 |
|---|---|
| `SKILL.md` | 入口路由、决策点、章节规划启发式、分轮规范、schema 定义 |
| `references/` | 决策点 UI 文本、四份页面模板、agent prompt 规范、Phase Δ 协议、meta schema 与字段速查、章节规划启发式、SKILL_ROOT 协议、模板复用矩阵、用户偏好 |
| `scripts/` | 15 个辅助脚本（见 `scripts/README.md`） |
| `docs/usage.md` | 使用手册：参数表、决策点、Phase Δ 分流、故障排查 |
| `docs/maintainers.md` | 维护手册：升级流程、收尾固定段、hash 协议、兼容矩阵 |
| `design-notes/` | 每次升级的 plan 存档（`v<版本>-<主题>.md`）与 `INDEX.md` |
| `.upgrade/` | `--upgrade` 的中间产物（pending plan、docs-followup） |
| `CHANGELOG.md` | 版本记录；顶部 `<!-- skill-content-hash -->` 供自检 |

## 安装

```
# 本体放全局目录，各 agent 用软链接指向它
~/.agents/skills/repo-wiki/            ← 本体
~/.claude/skills/repo-wiki -> ../../.agents/skills/repo-wiki
```

其他 agent（Codex / Gemini CLI / opencode 等）同样建软链接到本体即可；opencode 会把 `~/.claude/skills/*/SKILL.md` 识别为 command。

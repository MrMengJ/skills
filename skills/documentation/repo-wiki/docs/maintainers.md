# repo-wiki 维护手册

<!-- 重建说明：原件于 2026-09-03 丢失，本文按 SKILL.md「--upgrade 分支」「兼容矩阵」与 scripts/ 实际实现重写（2026-09-04）。 -->

## 1. 文件与职责

| 文件 | 修改时机 | 由谁改 |
|---|---|---|
| `SKILL.md` | 流程 / 规范变化 | `--upgrade` 主体步骤 |
| `references/*.md` | 决策点文案、模板、协议变化 | 同上（模板改动要升 `template-version`） |
| `references/meta-schema.json` | schema 字段变化 | 同上，且要升 `schema_version` + 写迁移脚本 |
| `scripts/*` | 接口或行为变化 | 同上；改接口必须同步 `scripts/README.md` 与 `docs/usage.md` § 3 |
| `README.md` / `docs/usage.md` / `docs/maintainers.md` | 用户可见行为变化 | 收尾第 7 步审查 |
| `CHANGELOG.md` / `design-notes/` | 每次升级 | `release-finalize.sh` 自动 |

内容 hash 覆盖 `SKILL.md + references/** + scripts/**`；README / docs / CHANGELOG / design-notes 不计入。

## 2. 升级流程（`/repo-wiki --upgrade`）

### 三档执行路径

| Level | 环境 | 收集 plan 的方式 | 执行主体 | 收尾 |
|---|---|---|---|---|
| 1 | 有 plan 模式（Claude Code） | 进入 plan 模式 → 生成 plan → ExitPlanMode | agent 执行 | `release-finalize.sh` |
| 2 | 有对话无 plan 模式（Cursor / Cline / opencode …） | 按问题框架逐项收集 → markdown 呈现确认 → 写 `.upgrade/pending-plan-<ts>.md` | agent 执行 | 同上 |
| 3 | 纯 CLI | `scripts/upgrade-cli.py --interactive` | 维护者手工 | 同上 |

### Plan 模板（4 节必填 + 固定收尾）

```markdown
## 改造背景 — 问题 / 需求描述
## 改造目标 — 完成后有什么不同
## 用户文档影响分析（禁止跳过）
  1. 是否影响 README.md 快速开始 / 命令表 / 平台表？
  2. 是否影响 docs/usage.md 决策点 / Phase Δ / 故障排查？（参数变化要同步 § 0 HELP-PARAM 表）
  3. 是否影响 docs/maintainers.md 升级流程 / 自检清单？
## 改造主体步骤（含文档同步）
## 收尾（固定段，禁止修改）
```

`design-notes-lint.py` 检查前四节是否齐全。

### 收尾固定段（8 步，`scripts/release-finalize.sh` 是单一可信源）

```bash
scripts/release-finalize.sh --plan <plan.md> --new-version 2.2.0 --topic-slug add-go-support [--summary "一句话"] [--commit]
```

1. 拷贝 plan → `design-notes/v<版本>-<slug>.md`
2. 追加 `design-notes/INDEX.md` 一行
3. 更新 `SKILL.md` 顶部 `<!-- skill-version -->`（以及标题 / 开场卡片中的版本号）
4. `skill-self-check.py --print-hash` 重算 hash → 写 `CHANGELOG.md` 顶部
5. `CHANGELOG.md` 插入 `## [版本] - 日期` 条目（已存在则跳过；`--summary` 作为首条）
6. `design-notes-lint.py` + `skill-self-check.py --strict`
7. `docs-drift-helper.py --plan <plan>`：三选一「已无需更新 / 已更新 / `--followup` 写入 `.upgrade/docs-followup.md`」
8. `--commit` 时 `git add -A && git commit -m "chore(skill): upgrade to v<版本> — <slug>"`（skill 目录非 git 仓库则跳过）

### `--recover`

直接改了 SKILL.md 没走 `--upgrade` → 开场卡片提示漂移 → `scripts/release-finalize.sh --recover` 只跑第 4–7 步（版本号沿用 SKILL.md 现值，CHANGELOG 已有该版本条目则不新增）。

## 3. 内容 hash 协议（v1）

```
hash = sha256( Σ_{文件按路径排序} "<相对路径>\n<内容(剔除 skill-content-hash 行)>\n" )[:16]
文件范围 = SKILL.md + references/** + scripts/**（跳过 __pycache__）
```

- 记录位置：`CHANGELOG.md` 顶部 `<!-- skill-content-hash: <16hex> -->`；`SKILL.md` 顶部同名行保持 `PLACEHOLDER`（原版即如此，避免自引用）。
- `skill-self-check.py` 同时比对 `SKILL.md` 的 `skill-version` 与 CHANGELOG 最新条目版本号。
- 默认不阻断 wiki 生成；只有 `--strict`（收尾第 6 步）才返回非 0。

## 4. 版本与兼容矩阵

```
skill v2.0.x  ⇄  schema v2    ⇄  template v2.x.y
skill v2.1.x  ⇄  schema v2.1  ⇄  template v2.x.y（不变）
```

- **skill 版本**：语义化；补丁版只改文案 / 修 bug，次版本加决策点或脚本子命令，主版本改 schema 不兼容。
- **schema 版本**：`index.schema_version` 整数；升 major 时必须写 `migrate-meta.py --from-version N --to-version M` 路径、CHANGELOG 标注不兼容、更新本矩阵。`delta-schema.py` 的 `SUPPORTED_SCHEMA_VERSION` 同步改。
- **模板版本**：模板文件头 `<!-- template-version: N -->`；`delta-schema.py` 的 `SUPPORTED_TEMPLATE_VERSIONS` 同步改；Phase Δ.6 负责提示漂移。

## 5. 自检清单（发布前）

- [ ] `python3 scripts/skill-self-check.py --skill-root . --strict`
- [ ] `python3 scripts/design-notes-lint.py --skill-root .`
- [ ] `python3 -m py_compile scripts/*.py && bash -n scripts/release-finalize.sh`
- [ ] 找一个已生成的 wiki 跑一遍：`delta-schema.py validate` → `delta-git.py precheck / affected-pages` → `delta-conflicts.py check` → `check-dead-links.py` / `check-mermaid.py` / `wiki-stats.py`
- [ ] `python3 scripts/help.py` 输出的参数表与 `docs/usage.md` § 0 一致
- [ ] 脚本新增或改名任何子命令 / 参数后，`scripts/README.md`、`docs/usage.md` § 3 与 `references/phase-delta-protocol.md` 的调用速查表三处同步更新（评测里反复出现的漂移点：脚本有的 flag 协议里没写，agent 就不会用）
- [ ] README 命令表、平台表与 SKILL.md 入口路由一致

## 6. design-notes 约定

- 文件名 `v<主>.<次>.<补>-<slug>.md`，slug 小写英文连字符。
- `INDEX.md` 表格：`| 版本 | 主题 | 文件 | 日期 |`，由 `release-finalize.sh` 追加。
- 每份 note 保留 plan 原文（四节 + 固定收尾），事后不改写；如需勘误在文末追加「事后备注」。

## 7. 备份与恢复

- 本体放 `~/.agents/skills/repo-wiki/`，各 agent 目录只放软链接；任何「同步 / 安装」工具在写入前先确认目标不是软链接自引用。
- 建议把本体目录初始化为 git 仓库并推到私有远端（`release-finalize.sh --commit` 会自动提交）。
- 应急来源：opencode 会话数据库（`~/.local/share/opencode/opencode.db`）会保存 skill 注入正文和 read 过的文件；Claude Code 会话记录默认 30 天清理，不可依赖。2026-09-04 的恢复过程见 `CHANGELOG.md` 末尾。

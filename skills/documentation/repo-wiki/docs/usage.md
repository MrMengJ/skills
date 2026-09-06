# repo-wiki 使用手册

<!-- 重建说明：原件于 2026-09-03 丢失，本文按 SKILL.md、references/ 与 scripts/ 的实际接口重写（2026-09-04）。 -->

## § 0 参数速查（HELP-PARAM，`scripts/help.py` 直接读取此表）

<!-- HELP-PARAM-START -->
| 参数 | 作用 |
|---|---|
| （无参数） | 首次生成：Phase 0 调研 → D1–D5 决策点 → 分轮生成 → 验证；已有 `.wiki-meta/` 时询问 (a) 增量更新 (b) 从头重建 (c) 查看上次同步状态 |
| `--update` | Phase Δ 增量更新：schema 校验 → git 预检 → 差异收集 → 反向映射 → 冲突检测 → 汇总决策 → 模板漂移 → 重写 → 孤儿扫描 → 收尾 |
| `--rebuild` | 备份现有 wiki 为 `<wiki>.bak-<TIMESTAMP>/` 后重走完整生成 |
| `--dry-run` | 只展示差异与受影响页面，不写任何文件 |
| `--from <commit>` | 覆盖 `last_synced_commit` 作为增量起点；早于上次同步时显式警告，默认转 dry-run |
| `--platform=tier1/2/3` | 强制交互层级（结构化工具 / 文本选项 / 纯 CLI），跳过能力探测 |
| `--upgrade` | 升级 skill 自身：Level 1 plan 模式 / Level 2 对话收集 / Level 3 `scripts/upgrade-cli.py` |
| `--upgrade --recover` | 手改 SKILL.md 后只运行收尾固定段补 hash / CHANGELOG / design-notes |
| `--help`, `-h` | 打印帮助后退出，不进入任何 Phase |
<!-- HELP-PARAM-END -->

**参数复述原则**：调度器不硬解析参数，先复述解析结果（模式 / 范围 / 起始 commit / 是否 dry-run），用户确认后再执行。

## § 1 首次生成流程

1. **开场卡片**：打印 4 件事与元命令提示；`skill-self-check.py` 自动运行，hash 漂移时追加一行警告（不阻断）。
2. **静默调研**：探测命令在内部跑，只展示摘要卡（类型 / 入口 / fork / 规模）。检测到 ≥2 种语言信号时必须问「单语言 + 工具链 / 多语言 monorepo / 多服务集群」。
3. **决策点**（完整 UI 文本见 `references/decision-points.md`）：

| 决策点 | 问题 | 写入 |
|---|---|---|
| D1.1 | 首要受众（单选） | `audience.primary` |
| D1.2 | 次要受众（多选 / 跳过） | `audience.secondary` |
| D2 | 输出语言 | `output_language` |
| D3 | 章节草稿确认（全部接受 / 逐章调整 / 自由文本 / 重新调研） | `chapters[]` |
| D4 | 输出目录 | `wiki_root` |
| D5 | mermaid 图表 | `run_config.mermaid_enabled` |
| C1 | 第一轮结束后：暂停偏好 | `run_config.pause_between_rounds` |

所有决策点末尾附 `[ ? | back | skip-all | edit-schema | cancel ]`，这些是元命令不是选项。

4. **分轮生成**（决策点答案已在上下文里时不再逐项询问，只复述一次）：轮 1 基础层（同时产出 `GLOSSARY.md` 术语表）→ 轮 2 实体层 → 轮 3 领域层 → 轮 4 外围层 → 最后一轮验证；每轮内可并行派工作 agent（6–8 页/agent），轮间串行。章节规划启发式见 `references/chapter-planning-heuristics.md`。
5. **验证轮**：

```bash
python3 $SKILL_ROOT/scripts/check-dead-links.py --wiki-root $WIKI_ROOT
python3 $SKILL_ROOT/scripts/check-mermaid.py    --wiki-root $WIKI_ROOT
python3 $SKILL_ROOT/scripts/wiki-stats.py       --wiki-root $WIKI_ROOT --min-chars <门槛> --per-page
```

通过标准：页数 ≥ 目标 95%；每章偏差 ≤ ±20%；`.followup.md` 待办 ≤ 10%；死链 0；mermaid 无字面 `\n`；`GLOSSARY.md` 存在；每页汉字数达到按规模分档的门槛（源文件 <50 取 1200、50–300 取 1800、>300 取 2200，ADR 再降 300）。注意 `wiki-stats.py` 报告里「汉字」与「非空白」是两个口径，门槛看前者。

6. **收尾**：`INDEX.md` 末尾追加「如何更新本 wiki」（含 `<!-- repo-wiki-managed -->`）、写 `HOW-TO-UPDATE.md`、`index.json._comment` 写常用命令、确认 `runtime.json` 已 git-ignored。

## § 2 增量更新（Phase Δ）

完整协议见 `references/phase-delta-protocol.md`；下表列出每步脚本与结果分流。

| 步骤 | 脚本 | 结果分流 |
|---|---|---|
| Δ.-1 | `delta-schema.py validate --meta-dir … --repo-root .`（`--repo-root` 省了就不查 source_files 存在性） | `symbolic_base` → 基线不是 40 位 hash，先纠正再继续；`json_syntax` / `type_error` / `missing_field` → abort 让用户修；`source_is_directory` → 该页 primary source 写成了目录（supporting 写目录只进 `notes[]` 不报错），展开成具体文件；`missing_source_file` → 逐条问 renamed / deleted / typo / skip；`schema_version_ahead` → 跑 `migrate-meta.py`；`template_version_ahead` → 提示升级 skill；`staging_residue: true` → 续传 / 丢弃 / 看 diff |
| Δ.0 | — | 复述参数；取消词典「算了 / 不要了 / cancel / 退出 / 等等 / 先不弄了 / 等下」 |
| Δ.1 | `delta-git.py precheck --meta-dir … [--base <hash>]` | `unreachable_commit` → merge-base / 全量重建 / 手动指定；`dirty_workdir` → include / exclude；`branch_mismatch` → 是否继续 |
| Δ.2 | `delta-git.py collect --base <commit>` | `split_candidates` 非空时逐条询问是否更新 `source_files` |
| Δ.3 | `delta-git.py affected-pages --meta-dir … --base <commit> --no-truncate`（输出含 `reasons` 与 `needs_review`） | `primary` 重写 / `supporting` 提示 / `deprecated` 候选删除；`renamed_sources` 提示更新 source_files；`truncated` 时分批 |
| Δ.4 | `delta-conflicts.py check --meta-dir … --wiki-root …` | 每条 `conflicts[]` 三选一：保留现存 / 覆盖 / 输出 `.new` 做 diff |
| Δ.5 | — | 四组展示 + 总体决策：全量执行 / 逐组确认 / 仅 dry-run / 取消 |
| Δ.6 | — | 模板漂移三选一；永久抑制写 `template_upgrade_suppressed_until` |
| Δ.7 | `delta-schema.py write-staging` → 派 agent → 每页 `update-page` → `commit-staging`；失败 `rollback-staging` | 页面 sha 用 `delta-conflicts.py hash --file <页.md>` 取得 |
| Δ.8 | `delta-git.py orphan-scan --meta-dir … --repo-root . --base <基线> --no-truncate` | 展示 `ignore_patterns_used` 问是否调整；`clusters[]` 非空时提示新增章节 |
| Δ.9 | `delta-schema.py update-sync --meta-dir … --commit HEAD --branch <name>` | 用 Read 检查 `INDEX.md` marker；打印完成报告 |

`--dry-run` 执行 Δ.-1～Δ.6 与 Δ.8（都是只读），跳过 Δ.7 重写与 Δ.9 收尾，不写 `runtime.json`。

## § 3 脚本速查

所有脚本 Python ≥ 3.8、仅标准库；delta-* 系列输出单行 JSON，exit 0 + `"ok": false` 表示需要人工决策，exit 1 表示脚本错误。

| 脚本 | 子命令 / 参数 | 备注 |
|---|---|---|
| `check-dead-links.py` | `--wiki-root` `[--ignore-pattern glob]…` `[--strict]` | 默认退出码 0，`--strict` 有死链返回 1 |
| `check-mermaid.py` | `--wiki-root` `[--strict]` | 检查字面 `\n`、未闭合、空块 |
| `wiki-stats.py` | `--wiki-root` `[--min-chars N]` `[--per-page]` | 页数 / 字符 / mermaid / 待办比例 / GLOSSARY.md 是否存在 + 逐页汉字数与未达标清单；页数已排除 INDEX / HOW-TO-UPDATE / GLOSSARY / 章节 README |
| `delta-schema.py` | `validate` `read` `write-staging` `commit-staging` `rollback-staging [--keep]` `update-page --page --sha256 --template-version [--status]` `update-sync --commit --branch [--repo-root]` | `--page` 的 `pages/` 前缀与 `.json` 后缀可省略 |
| `delta-git.py` | `precheck [--base]` `collect [--head] [--include-workdir]` `affected-pages [--no-truncate]` `orphan-scan --repo-root [--base|--since] [--no-truncate] [--ignore-patterns]` | rename 视为「变更」而非「删除」；`--base`（= `--since`）只报自基线以来新增的孤儿，默认截断 200 条 |
| `delta-conflicts.py` | `check --meta-dir --wiki-root`；`hash --file` | normalize = 去 BOM + LF + 去尾空行（protocol v1）；页面 json 里存了 `content_sha256_no_whitespace` 才能判定纯空白改动 |
| `diff-impact.py` | `--meta-dir --base [--head] [--repo-root]` | affected-pages 的人类可读版 |
| `migrate-meta.py` | `--from-version 1 --to-version 2 --meta-file …`；`--from-version 2 --to-version 2 --meta-dir …` | v1 单文件 → v2 拆文件；v2 就地补缺省字段 |
| `help.py` | `[--skill-root]` | 版本号读 SKILL.md；参数表读本文 § 0 |
| `skill-self-check.py` | `--skill-root [--print-hash] [--strict]` | 见 `docs/maintainers.md` hash 协议 |
| `design-notes-lint.py` | `--skill-root` | INDEX 登记、命名、四小节 |
| `docs-drift-helper.py` | `--skill-root [--plan] [--followup "…"]` | 收尾第 7 步 |
| `upgrade-cli.py` | `--interactive` / `--no-prompt --from-json` | Level 3 入口 |
| `release-finalize.sh` | `--plan --new-version --topic-slug [--commit] [--summary]`；`--recover` | 收尾固定段 8 步 |

## § 4 故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| 开场卡片下出现「skill 内容已变更但 CHANGELOG 未更新」 | 直接改了 SKILL.md / references / scripts 没走 `--upgrade` | `/repo-wiki --upgrade --recover` 或 `scripts/release-finalize.sh --recover` |
| `validate` 报 `missing_source_file` 且 path 是目录名 | 某页 `source_files[].path` 写成了目录或非字符串 | 按提示选 typo 修正该页 json；目录路径无法参与 diff 反向映射 |
| 首次 `--update` 把所有页都报成「手动改动冲突」 | 页面 sha256 是自行实现 normalize 算的，与脚本口径不一致 | 用 `delta-conflicts.py hash --file <页.md>` 逐页重算并 `update-page` 回填；以后一律用脚本取值 |
| 某一章永远不出现在受影响列表里 | 该页 primary `source_files` 写的是目录 | v2.1.4 起 `validate` 会报 `source_is_directory`；把目录展开成驱动这一页内容的 1-3 个具体文件 |
| `--update` 报「没有变化」但代码明明改了 | 旧产物 `index.json.last_synced_commit` 是字面量 `HEAD`（v2.1.0 之前 update-sync 的 bug） | v2.1.2 起 `validate` / `precheck` 会直接报 `symbolic_base`；从 INDEX.md 的「同步基线」或 `git reflog` 找回真实 hash，用 `--from <hash>` 跑一次，或改成完整 hash 后再 `--update`，并用 `precheck --base <hash>` 复检 |
| 首次生成收尾时才发现页面字数不够 | 靠目测估字数 | 分轮生成中途就用 `wiki-stats.py --wiki-root … --min-chars 1800` 逐页核对，它会直接列出不达标的页 |
| 孤儿扫描报出几千条，全是历史杂项 | 未加 `--since` | `orphan-scan --since <基线 hash>` 只看自基线以来新增的未覆盖文件；同时把 `docs/**`、`scripts/**`、i18n 文件补进 `ignore_patterns` |
| `precheck` 报 `unreachable_commit` | 上次同步 commit 被 rebase / 强推 / 分支切换 | 选 merge-base（脚本已给出 `merge_base` 字段）或 `--from` 指定起点 |
| `affected-pages` 返回 `truncated: true` | 受影响页 > 50 | 加 `--no-truncate` 或分批处理 |
| `conflicts` 全部页面都冲突 | 页面曾被批量格式化 / 换行符变化 | 用 `delta-conflicts.py hash` 重算并 `update-page`，或 Δ.4 选覆盖 |
| `commit-staging` 报 `no_staging` | 未先 `write-staging` 或已被 rollback | 重新 `write-staging` |
| 工作 agent 报 `stalled: no progress for N seconds` | 违反逐页处理规则 | 只对未写出的页重派 agent，规则放 prompt 最前，减少到 3–4 页/agent |
| mermaid 图里出现字面 `\n` | 节点标签用了 `\n` | 改 `<br/>`；`check-mermaid.py` 会定位到行 |
| `orphan-scan` 孤儿数千个 | schema 未设 `ignore_patterns` | 在 `index.json` 补 `ignore_patterns`（脚本按 `primary_type` 给默认值） |
| `help.py` 报错 | SKILL.md 缺 `<!-- skill-version -->` | 补回该行；调度器遇 help.py 失败会展示 stderr 并退出 |

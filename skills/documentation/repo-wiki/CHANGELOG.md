<!-- skill-content-hash: 63f9be9a0e89f062 -->
# Changelog

All notable changes to the `repo-wiki` skill will be documented in this file.
版本日期以本机 Claude Code 会话记录、生成产物中的 `runtime.json` / `HOW-TO-UPDATE.md` 为准。

## [2.1.6] - 2026-09-05
### Fixed
- **v2.1.5 引入的 bug**：`source_root` 的默认值写成了 `.`，但它相对 wiki 根目录解析，对最常见的 `<项目>/.wiki` 布局正确值是 `..`；照文档填会把源码根指到 wiki 目录自己。
- `affected-pages` 存在**静默的第四桶**：`source_files` 为空、或 primary 只被删了一部分的页面，从 primary / supporting / deprecated 三组里全部漏掉，既不重写也不提示。现在归入 `needs_review` 并在 Δ.5 单列 E 组。
- `delta-conflicts.py check` 不输出 exit-code 约定承诺的 `ok` 字段。
### Changed
- **最低字数改为按项目规模分档**：源文件 <50 取 1200、50–300 取 1800、>300 取 2200，ADR 再降 300。固定 1800 对小项目不合理——连续两轮评测里 4 页首稿全部不达标（1486–1640），各多花一轮补写。同时说明报告里「汉字」与「非空白」是两个口径（实测相差 2.3 倍），门槛看前者。
- `affected-pages` 输出新增 `reasons`：每页命中了哪些路径、什么角色、改动还是删除。此前只返回页面名，两轮评测里 agent 都为了拿命中原因重写了一遍反向映射。
- 章节 README 的三项要求（文件存在、有对应 `README.json`、json 的 `page_type` 与 `source_files`）收拢到 SKILL.md 一处；此前散在三个文件里，漏写不会有任何报错。
- 非交互模式的覆盖面从 Phase 0 扩到全文：所有写着「必须询问用户」的地方（含多语言信号识别）在非交互下取探测到的首选值并在复述里标出；Δ.-1 与 Δ.5 的确认给出明确默认值。
- Δ.3 / Δ.8 的正文代码块补齐速查表里已有的 `--no-truncate` / `--base`；Δ.6 说明内置模板版本取自四份模板文件头部的 `<!-- template-version -->`，没有专门脚本。
### Evals
- iteration-5（v2.1.5）：3 条用例 22/22 全通过，v2.1.4 与 v2.1.5 确认无回归。五轮累计：恢复版 21/22，其后四轮均 22/22，无 skill 基线始终 9/22。
- 本版改动未经 eval 验证。

## [2.1.5] - 2026-09-05
### Fixed
- **`secondary` 角色被整个忽略**：2026-07 期间生成的约 20 份 wiki 用 `secondary` 而非 schema 规定的 `supporting`。反向映射只认 `primary` 和 `supporting`，这些条目既不触发重写也不产生提示，是静默假阴性。现在脚本按别名兼容，`validate` 在 `notes[]` 提示，`migrate-meta.py --from-version 2 --to-version 2` 可一键改写。
- v2.1.4 的目录型 source 规则太宽：真实产物里 29 处目录型 source 有 28 处是 `supporting`，「仓库结构与目录地图」这类页面列目录是合理写法。现在只有 `primary` 写目录才报 `source_is_directory`，`supporting` 进 `notes[]`。
### Added
- `index.json` 新增可选 `source_root`：`source_files[].path` 相对于哪个目录。工作区级 wiki 的路径是相对工作区根写的，此前没有任何字段记录这点，用单个仓库根去校验会把全部源码报成缺失。
- `validate` 新增 `source_root_mismatch` 提示：超过半数源码路径缺失时直接指出多半是根目录给错了，不要照着 `missing_source_file` 逐条改数据。整理这批修复时我自己就因此误判过一次。
- `phase-delta-protocol.md` 补 `source_is_directory` 的批量处理三选一（逐页展开 / 本次跳过并在报告里单列 / 转 `--rebuild`）。
### Evals
- 本版与 v2.1.4 的改动均未经 eval 验证。

## [2.1.4] - 2026-09-05
### Fixed
- **目录型 source 路径被静默放行**：`validate` 原来用 `exists()` 判断 `source_files[].path`，目录一律通过。真实产物里第 08 章的 source 就是目录 `.agents/notes`，而它同时命中 `ignore_patterns`，于是该章在每次增量更新里都是假阴性——底下的笔记树改了 174 个文件也不会被标记为受影响。现在报 `source_is_directory`（options: expand/typo/skip）。
- `primary_type` 枚举补 `desktop-app` / `frontend-app` / `nodejs-cli`；Electron 项目此前只能落到 `other`。
### Added
- `wiki-stats.py` 报告 `GLOSSARY.md` 是否存在。它自 v2.1.1 起是硬要求，但此前没有任何检查项，缺失也不会有人发现。
- `meta-schema-fields.md` 新增「normalize 口径」一节，写清四步算法，并明确要求用 `delta-conflicts.py hash --file` 取值。评测中 agent 照原先那句话自行实现，算出的 hash 与脚本不一致；若不察觉，首次 `--update` 会把每一页都误判为手动改动冲突。
- 验证通过标准新增两项：`GLOSSARY.md` 存在、每个章节 README 都有对应的 `README.json`（后者此前只写在参考文件的兼容说明里，Δ.4 覆盖不到没有 json 的 README）。
- 首次生成收尾明确 `last_synced_commit` 要写 `git rev-parse HEAD` 的完整 40 位 hash。
### Evals
- iteration-4（v2.1.3）：3 条用例 22/22 全通过，与 v2.1.1 持平，无回归；无 skill 基线 9/22。
- 澄清一条误报：dry-run 评测称「`update-sync --commit HEAD` 每次首跑都产出不可用的 HEAD 基线」。实测该脚本会 `rev-parse` 展开并写入完整 hash，iteration-2 首次生成产出的也是 40 位 hash。测试仓库里的坏值是 2026-08 原版脚本留下的历史产物。
- 本版改动未经 eval 验证。

## [2.1.3] - 2026-09-05
### Fixed
- `phase-delta-protocol.md` 的 Δ.-1 示例命令漏了 `--repo-root`。`delta-schema.py` 只在给了它时才检查 `source_files` 是否真实存在，所以照抄命令的调度器永远触发不到协议里长篇描述的 `missing_source_file` 分流——而源码被删改恰恰是 schema 失效最常见的原因。
- `orphan-scan` 在 200 条静默截断且没有 `--no-truncate`，与 Δ.3 要求 `affected-pages` 加该参数的做法不一致；评测中 agent 只能自行改脚本常量取全量。现已补上，并把 `--since` 增设 `--base` 别名与其他子命令统一（`--since` 保留兼容）。
### Added
- `phase-delta-protocol.md` 新增「符号引用基线的纠正」三步：从 INDEX.md 的同步基线取短 hash → `git rev-parse` 展开为 40 位 → 显式透传给 Δ.1/Δ.2/Δ.3/Δ.8（脚本之间不互相记忆）。dry-run 下不写回 `index.json`，只在报告里给出修正命令。
- Phase Δ 补齐非交互模式条款，与 Phase 0 对齐；Δ.5 说明在 `--dry-run` 下总体决策只剩「继续 / 取消」两项，不要把「仅看 dry-run」列为选项。
### Evals
- iteration-3（v2.1.2）：`--dry-run` 7/7、`--help` 5/5。`symbolic_base` 拦截确认有效——agent 在 Δ.-1 即发现基线为字面量 `HEAD`，自行展开真实 hash 后用 `--base` 继续，不再像 v2.1.1 那轮绕行。首次生成一条在写完 4 页正文（全部通过新的逐页字数检查）后被 API 配额中断，非 skill 缺陷，待配额恢复后补跑 iteration-4。
- 本版改动尚未经 eval 验证。

## [2.1.2] - 2026-09-05
### Fixed
- **符号引用基线被静默放行**：`index.json.last_synced_commit` 写成 `HEAD`、分支名或短 hash 时，`validate` 只查类型、`precheck` 认为 HEAD 从 HEAD 可达、`collect --base HEAD` 返回空 diff，整条增量链路报「0 页受影响」。现在 `delta-schema.py validate` 与 `delta-git.py precheck` 都会报 `symbolic_base`（options: resolve/specify/rebuild），`meta-schema.json` 也给该字段加了 40 位 hex 约束。已有产物中确实存在这种坏值。
- `delta-conflicts.py` 的 `is_whitespace_only` 不再硬编码为 `false`：页面 json 存有新增的可选字段 `content_sha256_no_whitespace` 时据此判定，否则返回 `null` 交人工确认；`hash` 子命令同时输出两种 sha256。
### Added
- `wiki-stats.py` 逐页字数核对：`--min-chars`（默认 1800）按汉字统计并列出不达标页面，`--per-page` 列全部；计数前剔除代码块与 mermaid。总页数改为排除 `INDEX.md` / `HOW-TO-UPDATE.md` / `GLOSSARY.md` 与章节 `README.md`，可直接与 `target_pages` 比较。此前该门槛没有任何脚本支撑，评测中一次首次生成有约四分之一时间花在自行写计数器并返工补写。
- `delta-git.py precheck --base <hash>`：纠正基线后可用脚本复检 Δ.1。
- `delta-git.py orphan-scan --since <commit>`：只报自基线以来新增且未被覆盖的文件。评测中同一仓库不加该参数报 3584 条历史杂项，加上后降到 204 条并直接指向 10 个新增包。
### Changed
- `phase-delta-protocol.md` 新增「dry-run 的边界」一节：Δ.-1～Δ.6 与 Δ.8 只读照跑，Δ.7 / Δ.9 跳过，不写 `runtime.json`；此前该边界只写在 `docs/usage.md` 里，而调度器从不被要求读该文件。
- Δ.3 汇总展示改为推荐 `--no-truncate`（默认截断 50 条是为防刷屏，不是要求分批）。
- SKILL.md：Δ.-1 的「4 类分流」改为按协议表述；收尾固定段第 3 步的版本号字面量改为占位符；最低字数按页面类型区分（概念/混合/参考 ≥1800 汉字，决策记录 ≥1500）并要求用脚本核对；新增「非交互模式」说明（答案已在上下文里时不再逐项询问）。
- `scripts/README.md` 注明 `diff-impact.py` 是 `affected-pages` 的人类可读包装，并补齐各脚本新增参数；`docs/maintainers.md` 自检清单加入「脚本参数变更需三处同步」。
### Evals
- iteration-2（v2.1.1）带 skill 22/22 断言通过，无 skill 基线 9/22；iteration-1（恢复版 v2.1.0）21/22。
- 描述触发优化未采纳：`skill-creator` 的 `run_eval.py` 并发调用 `claude -p` 且丢弃 stderr，限流导致的失败被静默计为「未触发」，五轮均呈现「精确率 100% / 召回率 0%」的全 False 特征；改用干净串行探针复测，原描述在 3 条正向查询中正确触发 2 条。故保留原描述。

## [2.1.1] - 2026-09-04
### Fixed
- SKILL.md「最终验证规范」改为 `--wiki-root` 调用三个检查脚本（原件用位置参数，脚本不接受）。
- 开场卡片的 `skill-self-check.py` 自动运行补上 `--skill-root $SKILL_ROOT`。
- `scripts/delta-git.py` 从 `wiki_root`（如 `./.wiki`）推导孤儿扫描忽略模式时错误剥掉了点号。
### Changed
- 渐进式披露：章节规划启发式 A–H、按受众生成顶层目录示例、页数 / 轮数经验值下沉到 `references/chapter-planning-heuristics.md`；`.wiki-meta` 字段速查与 v2.0 兼容说明下沉到 `references/meta-schema-fields.md`；模板复用矩阵与 SKILL_ROOT 协议在 SKILL.md 中压缩为指针。SKILL.md 457 → 397 行。
- SKILL.md 为 `references/template-reuse-matrix.md`、`references/user-preferences.md` 补充读取指引（此前无人引用）。
- 首次生成的轮 1 产出 `{{WIKI_ROOT}}/GLOSSARY.md`（四份模板均要求术语与之一致）；页数比对说明扣除章节 README 与 GLOSSARY。
- Agent Prompt 规范要求源码引用写从项目根起的完整相对路径。
### Evals
- 新增 `evals/evals.json`（首次生成 / `--dry-run` / `--help`）；iteration-1 带 skill 22/22 断言通过，无 skill 基线 9/22。

## [2.1.0] - 2026-05-15
### Added
- **三层目录结构强制**：`{{WIKI_ROOT}}/<受众目录>/<NN-章节>/<NN-页面>.md`，章节编号在各受众目录内独立从 01 起（不再跨受众连续编号）；每章必须有 `README.md` 门面。
- **交互执行规范（能力探测分层）**：Tier 1 有结构化交互工具（Claude Code `AskUserQuestion`）/ Tier 2 文本选项 / Tier 3 纯 CLI；探测结果缓存在 `runtime.json` 的 `platform_capabilities`，可用 `--platform=tierN` 覆盖。
- **方案 C 确定性脚本**：`delta-schema.py`（schema 校验 / staging 事务 / update-page / update-sync）、`delta-git.py`（precheck / collect / affected-pages / orphan-scan）、`delta-conflicts.py`（normalize 后 sha256 冲突检测）；SKILL.md 只保留入口路由与生成规范，易出 bug 的 git / schema / 事务交给脚本。
- **Phase Δ 完整协议** `references/phase-delta-protocol.md`：Δ.-1 schema 校验四类分流、Δ.0 参数复述与取消词典、Δ.1–Δ.9 步骤与 exit code 约定。
- **`--upgrade` 三档路径**与**收尾固定段 8 步**（`scripts/release-finalize.sh` 为单一可信源）；`--upgrade --recover` 仅补元数据。
- `skill-self-check.py` 内容 hash 自检（开场卡片提示漂移，不阻断生成）；`design-notes-lint.py`、`docs-drift-helper.py`、`upgrade-cli.py`、`help.py`。
- `.wiki-meta/pages/` 改为按三层路径拆文件；`references/meta-schema.json` 记为 schema v2（v2.0 扁平 pages 仍可读，无需迁移）。
### Changed
- 决策点 D1 拆为 D1.1 首要受众（单选）+ D1.2 次要受众（多选）；D3 章节草稿按受众目录分组展示。
- 开场卡片、静默调研摘要卡、每轮产出报告卡固定文案。

## [2.0.0] - 2026-05-14
### Added
- skill 由 `repo-wiki-generator` 更名为 `repo-wiki`，统一触发词 `/repo-wiki`。
- **D1–D5 决策点**（受众 / 语言 / 章节草稿 / 输出目录 / mermaid）与 C1 暂停偏好；输出目录不再写死 `.repowiki`，改为询问。
- **增量更新**：`--update` / `--rebuild` / `--dry-run`，基于 `last_synced_commit` 的 git diff 反向映射受影响页；`.wiki-meta/` 元数据（index + 每页 `source_files` / `role` / `content_sha256_normalized`）。
- **`--upgrade` 自升级机制**：进入 plan 模式收集需求 → 执行 → plan 归档到 `design-notes/`（与 Claude 的 plan 目录解耦）。
- 章节规划改为启发式 A–H 从项目推导，不再内置「TypeScript 库 14 章」固定结构；轮数由章节数决定，每轮是否暂停由用户决定。
- 项目类型 / 入口点按 `package.json` / `pyproject.toml` / `go.mod` / `Cargo.toml` / `pom.xml` / 框架约定探测，不再写死 `index.ts`。
- 用户文档：`README.md`、`docs/usage.md`、`docs/maintainers.md`；升级收尾增加「审查是否要更新使用文档」。
- 用户级偏好 `~/.repo-wiki/user-preferences.json`。

## [1.0.0] - 2026-05-13
### Added
- 初代 `repo-wiki-generator`，诞生于 `@jecn/x6` 项目：沉淀《Repo Wiki 生成方法论》（概念型 vs 参考型文档、项目指纹分析、现有 wiki 审计、结构从项目推导、分批并行生成与质检），目标是覆盖广度对标并超越 Qoder repowiki、深度补齐「为什么这样设计」。
- 逐页处理规则（防 600 秒 watchdog）、mermaid 规范（禁止字面 `\n`）、源码引用精确到行号、`.followup.md` 补读待办化、验证脚本 `check-dead-links.py` / `check-mermaid.py` / `wiki-stats.py`。

---

## 恢复记录（2026-09-04）

2026-09-03 04:02 本 skill 目录被第三方同步工具的循环软链接 bug 清空。恢复来源与结果：

| 内容 | 状态 | 来源 |
|---|---|---|
| `SKILL.md` 正文 | 原文逐字恢复 | opencode 会话数据库中三次注入的 skill 正文（内容一致） |
| `references/` 8 份：decision-points / meta-schema.json / agent-prompt-spec / phase-delta-protocol / conceptual / mixed / reference / decision-log | 原文逐字恢复 | opencode 会话中的 read 工具记录 |
| `scripts/README.md`、`scripts/wiki-stats.py` | 原文逐字恢复 | 同上 |
| `references/` 3 份：skill-root-protocol / template-reuse-matrix / user-preferences | **重写** | 按 SKILL.md 对应章节与产物实例 |
| `scripts/` 其余 13 个脚本 | **按接口重写** | SKILL.md、phase-delta-protocol.md、scripts/README.md 记录的子命令 / 参数 / JSON 字段，以及当年真实运行输出；修正了原版 `delta-schema.py validate` 在 `source_files[].path` 非字符串时崩溃的问题 |
| `README.md`、`docs/`、`design-notes/`、`CHANGELOG.md` | **重写** | 会话记录中的开发历史 |

SKILL.md 的 YAML frontmatter（`name` / `description`）按 Claude Code 当时加载的 skill 清单还原。

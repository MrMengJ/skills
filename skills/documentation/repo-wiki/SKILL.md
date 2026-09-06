---
name: repo-wiki
description: 为任意代码项目生成结构化 wiki 的 AI agent skill。支持 4 类受众（维护者 / 使用者 / 新人 / 业务方）和多种项目形态（前端库 / 后端服务 / CLI / SDK / 单体业务 / 多语言 monorepo / 微服务集群 / fork 项目）。 Triggers on: "为这个仓库生成 wiki"、"生成代码文档"、"给 SDK 写 API 文档"、 "给新人写代码导览"、"给业务方讲清楚这个系统"、"document this codebase"、 "generate API docs for this library"、"write a contributor guide"、 "generate a repo wiki"、"帮我做文档"、"写一个 wiki"，or any request to create structured documentation covering architecture, APIs, business flows, or onboarding paths for a code project. Especially useful for repositories with complex internal mechanics that need systematic documentation across multiple audiences.
---

<!-- skill-version: 2.1.6 -->
<!-- skill-content-hash: PLACEHOLDER -->
<!-- skill-root-protocol: v1 -->

# Repo Wiki Generator v2.1.6

---

## 使用说明

这份 skill 是「驱动 AI agent 走完 wiki 生成全流程的决策框架」，不是「一份模板套所有项目」的固定脚手架。

**它做了什么**：标准化「调研 → 受众对齐 → 章节规划 → 分轮生成 → 验证 → 增量更新」全流程；提供四种页面模板 + 模板复用矩阵；给出防超时、防幻觉、Mermaid 规范、源码引用规范等通用工程约束；提供增量更新机制（git diff + 模板版本 + sha256 冲突检测）。

**它不做什么**：不预设章节结构、受众类型、页数/轮数/输出目录/命名风格/输出语言/图表密度，不假设项目是 fork，不绑定特定 AI 平台。

**支持项目形态**：前端库、后端服务、CLI、SDK、单体业务、多语言 monorepo、微服务集群、fork 项目、有 ADR 历史的非 fork 项目。

**平台中立**：流程术语（「决策点」「调度器」「工作 agent」）是抽象，Claude Code 是其中一种执行环境。决策点通过平台的「结构化交互工具」实现（各平台的具体工具名见 `references/decision-points.md`），watchdog 阈值为 600 秒。

---

## 术语表

| 中文 | English | 定义 |
|---|---|---|
| 决策点 | decision point | 需要用户选择才能继续的流程节点 |
| 调度器 | orchestrator | 驱动整个 wiki 生成流程的主 agent |
| 工作 agent | worker agent | 被调度器派发任务的子 agent，每次处理若干页 |
| 锚点材料 | anchor material | 工作 agent 写页面时引用的源码/IDL/DB schema 等 |
| 模板版本 | template version | 模板文件头的 `<!-- template-version: N -->` 版本号 |
| SKILL_ROOT | SKILL_ROOT | skill 根目录路径，解析协议见「SKILL_ROOT 解析协议」节 |
| 看门狗 | watchdog | 流式超时检测机制，agent 长时间无输出时被终止 |
| 结构化交互工具 | structured-input-tool | 平台提供的带选项 UI 的用户问询工具；存在与否由「能力探测协议」运行时判定 |

---

## 入口路由

调度器收到触发词后，**按以下顺序检测**：

```
检测 --help 或 -h 参数
  → 是 → python3 $SKILL_ROOT/scripts/help.py 输出 → 退出，不进入任何 Phase
  （help.py 失败时：显示 stderr 内容 → 同样退出，不进入 Phase）

检测 --upgrade 参数
  → 是 → 进入「--upgrade 分支」

检测 --update / --rebuild / --dry-run 参数
  → 是 → 进入 Phase Δ（增量更新模式）

检测 {{WIKI_ROOT}}/.wiki-meta/index.json 是否存在
  → 存在 → 询问用户：
      「检测到已有 wiki meta，您想：
       (a) 增量更新（推荐）  (b) 从头重建  (c) 仅查看上次同步状态
       [ ? 查看说明 | cancel 取消 ]」
    → a/b → Phase Δ
    → c → 展示 index.json 摘要后退出

无参数且无 .wiki-meta/ → 进入 Phase 0（首次生成）
```

**参数复述原则**：不硬解析，先复述解析结果（模式 / 范围 / 起始 commit / 是否 dry-run），等用户确认后再执行。

---

## --upgrade 分支（升级 skill 自身）

触发词：`/repo-wiki --upgrade` 或 `--upgrade --recover`

### 三档执行路径

调度器检测平台能力，按能力自动降级：

**Level 1（有 plan 模式，如 Claude Code）**：进入 plan 模式 → 收集需求生成 plan → ExitPlanMode → 执行主体 → 收尾固定段（8 步）

**Level 2（有对话能力，无 plan 模式，如 Cursor / Cline / Continue）**：
1. 向用户展示问题框架（改造背景 / 目标 / 文档影响分析 / 主体步骤），逐项收集答案
2. markdown 呈现完整方案，等用户确认
3. 确认后写到 `{{SKILL_ROOT}}/.upgrade/pending-plan-{{TIMESTAMP}}.md`
4. 执行主体步骤 + 收尾固定段

**Level 3（无 agent / 纯 CLI）**：`$SKILL_ROOT/scripts/upgrade-cli.py --interactive` 或 `--no-prompt`

所有 Level 最终汇聚到同一脚本 `scripts/release-finalize.sh`（收尾操作的单一可信源）。

### 升级 Plan 模板（必填 4 节）

```markdown
## 改造背景 — 问题/需求描述
## 改造目标 — 完成后有什么不同
## 用户文档影响分析（禁止跳过）
  1. 是否影响 README.md 快速开始/命令表/平台表？ → 是则步骤中包含「更新 README.md X 节」
  2. 是否影响 docs/usage.md 决策点/Phase Δ/故障排查？ → 是则步骤中包含「更新 docs/usage.md X 节（若有参数变化，同步更新 § 0 的 HELP-PARAM 表格）」
  3. 是否影响 docs/maintainers.md 升级流程/自检清单？
## 改造主体步骤（含文档同步）
## 收尾（固定段，禁止修改）
```

### 收尾固定段（8 步，所有 Level 均执行）

1. 拷贝 plan 文件到 `design-notes/v{{NEW_VERSION}}-{{TOPIC_SLUG}}.md`
2. 更新 `design-notes/INDEX.md`
3. 更新 SKILL.md 顶部 `<!-- skill-version: {{NEW_VERSION}} -->`（脚本按正则替换，不要写死某个版本号）
4. 重算 content-hash，更新 CHANGELOG.md 顶部 `<!-- skill-content-hash: ... -->`
5. 在 CHANGELOG.md 写新版本条目
6. 运行 `scripts/design-notes-lint.py` + `scripts/skill-self-check.py`
7. 用户文档审查（`scripts/docs-drift-helper.py`），三选一：已无需更新 / 已更新 / 写入 `.upgrade/docs-followup.md`
8. （可选）`git add -A && git commit -m "chore(skill): upgrade to v{{NEW_VERSION}} — {{TOPIC_SLUG}}"`

### `--upgrade --recover`（仅补元数据）

维护者直接编辑 SKILL.md 未走 `--upgrade` 时，`skill-self-check.py` 检测到 hash 漂移，开场卡片提示 `⚠️ skill 内容已变更但 CHANGELOG 未更新`。`--recover` 模式：跳过 plan 主体，**只**运行收尾固定段补全 hash/CHANGELOG/design-notes。

---

## Phase Δ — 增量更新模式

触发条件：用户传 `--update` / `--rebuild` / `--dry-run`，或在交互询问中选择增量更新。

**调度器进入 Phase Δ 前先 Read `$SKILL_ROOT/references/phase-delta-protocol.md` 获取完整步骤。**

**非交互模式**：与 Phase 0 一致——答案已在上下文里就不再逐项询问，只在 Δ.0 复述一次。Δ.-1 与 Δ.5 的确认在非交互下取默认值（`missing_source_file` / `source_is_directory` 取 skip，总体决策取「逐组确认」的只读部分），并把每一处所取的默认值写进最终报告。

**`--dry-run` 的边界**：Δ.-1 到 Δ.6 与 Δ.8 都是只读的，照常执行并汇报（用户问「会改哪些页」时通常也想知道新出现的未覆盖模块）；Δ.7 重写与 Δ.9 收尾跳过，`runtime.json` 不刷新。`skill-self-check.py` 在 Phase Δ 开头跑一次，只在卡片里提示 hash 漂移，不阻断。

| 步骤 | 要点 |
|---|---|
| **Δ.-1** schema 校验 | 调用 `delta-schema.py validate --meta-dir <wiki>/.wiki-meta/ --repo-root .` → JSON 错误列表，按 `type` 分流（含 `symbolic_base`：基线不是完整 40 位 hash，此时 diff 恒为空，必须先纠正）；全通过才进 Δ.0 |
| **Δ.0** 参数复述 | 复述模式/范围/commit/dry-run；取消词典：「算了/不要了/cancel/退出/等等/先不弄了」→ exit 不写文件 |
| **Δ.1** git 预检 | 调用 `delta-git.py precheck` → JSON issues 列表（commit 可达性 / 工作区 / 分支一致性）|
| **Δ.2** 差异收集 | 调用 `delta-git.py collect` → JSON diff（含 rename 链和拆文件候选）|
| **Δ.3** 反向映射 | 调用 `delta-git.py affected-pages` → primary/supporting/deprecated JSON |
| **Δ.4** 冲突检测 | 调用 `delta-conflicts.py check` → 冲突列表 JSON（normalize 后比对 `content_sha256_normalized`）|
| **Δ.5** 汇总展示 | 四组（primary/supporting/手动改冲突/deprecated）+ 总体决策四选一 |
| **Δ.6** 模板漂移 | 比对 `template_versions`；支持 `template_upgrade_suppressed_until` 持久化抑制 |
| **Δ.7** 执行重写 | 调用 `delta-schema.py write-staging / commit-staging` 做事务；子 agent 注入增量指令 |
| **Δ.8** 孤儿扫描 | 调用 `delta-git.py orphan-scan --base <基线> --no-truncate` → 孤儿/cluster JSON；`--base` 把「历来没覆盖的杂项」和「这次新长出来的模块」分开 |
| **Δ.9** 收尾 | 调用 `delta-schema.py update-sync`；INDEX.md marker 用 Read tool 检查；打印完成报告 |

---

## Phase 0 — 项目调研

### 开场卡片（Phase 0 第一段输出，必须在任何探测命令之前打印）

```
🪄 /repo-wiki v2.1.6
即将做 4 件事（你可随时输入 cancel 退出）：
  1. 静默调研项目（约 30 秒，外露摘要卡）
  2. 问你 5 个决策点（受众 / 语言 / 章节 / 输出位置 / 图表）
  3. 分轮生成 wiki（每轮结束暂停，可切换）
  4. 验证与收尾

下次更新只需 /repo-wiki --update（末尾会再提示）
任何时候输入 ? 查看帮助 | back 回上步 | cancel 取消
```

`python3 $SKILL_ROOT/scripts/skill-self-check.py --skill-root $SKILL_ROOT` 在此处自动运行：如发现 content-hash 漂移，在卡片下方追加 `⚠️ skill 内容已变更但 CHANGELOG 未更新`（不阻断 wiki 生成）。

### 静默调研（内部执行，不外露命令输出）

探测命令在内部跑，**不把 grep/find/git log 的输出直接印到对话**。结束后只展示摘要卡片：

```
✅ 项目调研完成
  类型：{project_type}（{detection_signal}）
  入口：{N} 个（{entry_points_summary}）
  Fork：{是/否}{fork_info}
  规模：~{module_count} 个模块，最近 6 个月 {commit_count} commits
```

**项目类型探测**（框架约定优先于 main 字段）：

| 检测信号 | 入口点探测 |
|---|---|
| `package.json` | 读 `main` / `module` / `exports` / `bin` 字段 |
| `pyproject.toml` / `setup.py` | 读 `[project.scripts]` / `entry_points`；检查 `manage.py`（Django）/ `main.py` 含 `FastAPI()` |
| `go.mod` | `find . -name "main.go"` + `cmd/*/`；每个 `cmd/<svc>/` 视为独立服务入口 |
| `Cargo.toml` | 读 `[[bin]]` + `src/main.rs` / `src/lib.rs`；CLI 工具扫 `clap` / `structopt` |
| `pom.xml` / `build.gradle` | 找 `Main` 类 / `mainClass`；扫 `@SpringBootApplication` |
| 框架约定（优先）| `next.config.*` / `nuxt.config.*` / `vite.config.*` / `pages/` `app/` `routes/` / `*/views.py` `*/urls.py` |
| 兜底 | README Quick Start 代码块、根 `Makefile` 目标 |

**多信号识别**：当 ≥2 个语言信号同时命中，**必须**询问用户：

```
检测到多种语言信号：{X, Y, Z}。这是：
(a) 单语言主项目 + 工具链辅助  (b) 真正的多语言 monorepo  (c) 多服务集群
[ ? | cancel ]
```

用户答案写入 `primary_type` / `secondary_types`，影响后续章节规划（启发式 E 或 G）。

**Anchor Material 5 类**：

| 类别 | 探测模式 |
|---|---|
| 接口契约 IDL | `*.proto` / `openapi*.yaml` / `*.graphql` / `*.thrift` |
| 数据库 schema | `migrations/` / `schema.sql` / `prisma/schema.prisma` / `*.dbml` |
| 部署清单 | `Dockerfile` / `docker-compose.*` / `k8s/*.yaml` / `helm/` / `terraform/` |
| 配置定义 | `config/*.yaml` / `.env.example` / `application*.yml` |
| ADR/RFC 既有文档 | `docs/adr/` / `docs/rfcs/` / `RFC-*.md` |

**是否 fork 检测**：检查 `git remote -v` 是否有 `upstream`、README 是否含「fork of」、`package.json` 是否仍指向上游包名。是 fork → 走完整 fork 分析（commit 热点、改动文件分布、上游版本）。

**commit 热点分析**（所有项目通用）：
```bash
git log --since="6 months ago" --name-only --pretty=format: | sort | uniq -c | sort -rn | head -20
```

---

## Phase 0 — 决策点序列（D1–D5）

### 交互执行规范（能力探测分层，v2.1+）

调度器在进入 Phase 0 第一个决策点前先做**能力探测**：
1. 查 `{{WIKI_ROOT}}/.wiki-meta/runtime.json` 的 `platform_capabilities.has_structured_input_tool` 缓存（若 wiki 已生成过）
2. 缓存缺失时尝试调用结构化交互工具——成功则缓存 `true`，捕获 `InputValidationError` / `tool not found` 则缓存 `false`
3. 用户可通过 CLI flag `--platform=tier1/tier2/tier3` 强制覆盖

- **Tier 1（有结构化交互工具）**：必须用结构化形式实现 D1.1 / D1.2 / D2 / D4 / D5 / C1；D3 因含自由文本编辑路径走混合模式（见 `references/decision-points.md` D3 节状态转移表）。
- **Tier 2（无结构化工具，有对话能力）**：沿用现有文本 prompt + 字母选项。
- **Tier 3（无 agent，纯 CLI）**：通过 stdin 提示实现（参见 `scripts/upgrade-cli.py`）。

具体工具名与平台映射见 `references/decision-points.md` 「Tier 1 工具绑定」节。

**所有决策点 prompt 末尾必须附加**：`[ ? 查看说明 | back 回上步 | skip-all 全部默认 | edit-schema 直接改 .wiki-meta | cancel 取消 ]`

**非交互模式**：调用方在首条消息里就给全了 D1–D5 的答案（自动化脚本、CI、批量为多个仓库生成时的常见形态），则不再逐项询问，只复述一次解析结果并继续；缺失项取默认值并在复述里标出。判断依据是「答案是否已经在上下文里」，不是某个 flag。**本文中所有写着「必须询问用户」的地方**（含多语言信号识别）在非交互下一律改为：取探测到的首选值，并在复述里标出这是自动选择的。

主流程识别元命令（不把它们当作选项内容）：`?` 展示说明 / `back` 回上步 / `skip-all` 取默认 / `edit-schema` 直接编辑 schema / `cancel` 退出。

**调度器在 Phase 0 末尾 Read `$SKILL_ROOT/references/decision-points.md` 获取完整 prompt UI 文本再提问。**

| 决策点 | 内容摘要 | schema 字段 |
|---|---|---|
| **D1.1** 首要受众（单选）| 维护者/使用者/新人/业务方（每项含预估页数描述）| `audience.primary` |
| **D1.2** 次要受众（多选/跳过）| 补充使用者/新人/业务方入门章节 | `audience.secondary` |
| **D2** 输出语言 | 中文 / 英文 / 跟随项目主语言（读用户偏好 `~/.repo-wiki/user-preferences.json` 作默认；字段与优先级见 `references/user-preferences.md`）| `output_language` |
| **D3** 章节草稿确认 | 按受众分组展示草稿；四选一：全部接受 / 逐章调整 / 自由文本编辑 / 重新调研 | — |
| **D4** 输出目录 | `./wiki/` / `./docs/wiki/` / `./.wiki/` / 自定义；写入 `wiki_root`，全文用 `{{WIKI_ROOT}}` 占位 | `wiki_root` |
| **D5** Mermaid 图表 | 启用（默认）/ 仅概念混合型 / 完全禁用 | `run_config.mermaid_enabled` |
| **C1** 暂停偏好 | **第一轮结束后**追问；三选一：每轮暂停 / 一气跑完 / 仅风险点暂停 | `run_config.pause_between_rounds` |

---

## 章节规划方法论（启发式 A–H）

调度器基于 Phase 0 调研结果产出 D3 草稿。**先选 1 条主启发式定骨架，再用其他启发式补章**；具体章节名称由 D3 用户确认落定，不强制任何硬编码命名。进入 D3 之前 Read `$SKILL_ROOT/references/chapter-planning-heuristics.md` 取各启发式的完整说明、按受众生成顶层目录的示例，以及页数 / 轮数经验值。

| 启发式 | 适用 | 骨架来源 |
|---|---|---|
| A 按分层 | 库 / 框架 / SDK | 模型层 / 视图层 / 控制器 / 注册系统 / 插件 / API 门面 / 工程化 |
| B 按模块 | monorepo / 多包 | 每个 package 一章 + 跨包协作 |
| C 按业务领域 | 单体业务系统 | 顶层 app 目录 + 数据库表簇 |
| D 按交叉切面 | 任何项目的补充章 | 工程化 / 可观测性 / 部署运维 / 业务切面 |
| E 按子系统 | 混合栈 / 前后端同仓 | frontend / backend / admin，各自再套 A–D |
| F 按旅程 / 路径 / 命令 | CLI / REST / RPC / 状态机 / 集成对接 | 子命令、API 资源域、状态机旅程、对接对象 |
| G 按部署单元 | 微服务 / 多 Lambda | 每个 `cmd/<service>` 一组 + 跨服务协议 |
| H 重大决策 | fork / ADR / 技术栈迁移 | `decision-log` 模板，`DECISION_TYPE` 区分 |

受众目录的命名词由 D3 用户落定（如 `维护者指南/`、`开发指南/`、`运维手册/`），但受众 / 章节 / 页面三层层级自 v2.1 起固定，工作 agent 不得输出扁平结构。

### 目录结构约束（v2.1+ 强制）

输出必须为三层结构：`{{WIKI_ROOT}}/<受众目录>/<NN-章节目录>/<NN-页面.md>`

- **受众目录**：命名为语义对齐的**全中文**名（如「维护者指南」「使用者指南」「业务说明」），不混入英文标识符
- **章节目录**：命名 `NN-中文主题`（两位数字编号 + 全中文短名，英文专有名词允许保留，如 `05-Git历史清理机制`、`06-LicenseKey更新流程`，但避免 `05-cleanGit-Git历史...` 这种含多个连字符的混名）。**编号在各受众目录内独立，不跨受众目录做全局连续编号**（例如：维护者指南/01-xxx … 09-xxx，使用者指南/01-xxx … 02-xxx）。
- **页面文件**：命名 `NN-中文标题.md`（两位数字章内序号 + 中文）
- 每个章节目录下的 `README.md` 章节门面有三项要求，缺一项都不会有任何报错，但会在增量更新时留下盲区：
  1. 文件存在，内容是本章定位 + 页面清单（每页一句话摘要）+ 阅读顺序
  2. 有对应的 `.wiki-meta/pages/<受众>/<章节>/README.json`，否则 Δ.4 冲突检测覆盖不到它
  3. 该 json 的 `page_type` 取所属章节的类型，`source_files` 至少写 1 个本章的代表性文件

调度器派发工作 agent 时必须在 prompt 中给出三层绝对路径，禁止仅给文件名（见 `references/agent-prompt-spec.md` 「页面输出路径格式」节）。

---

## 分轮执行规范

### 分轮依赖原则

```
轮 1（基础层）：项目全景 / 核心架构 / 数据模型 — 其他章节的引用基础
轮 2（实体层）：具体模块/包实体，依赖轮 1 的架构理解
轮 3（领域层）：业务逻辑 / 注册系统 / 插件 / 跨模块协作
轮 4（外围层）：框架集成 / 工程化 / 部署 / 示例应用
轮 N（验证轮）：单线程验证 + 收尾（死链 / Mermaid / stats），总是最后一轮
```

**轮数由章节数决定**（3-7 轮均可）。每轮内部可并行派多个工作 agent（建议 6-8 页/agent，最多 13 页），轮与轮之间串行。**默认行为**：每轮结束后暂停等用户确认，第一轮结束后追问 C1（暂停偏好切换）。

### 首次生成收尾

轮 1 除基础层页面外，还要产出 `{{WIKI_ROOT}}/GLOSSARY.md`（核心术语与定义）：四份模板都要求页面术语与 GLOSSARY.md 一致，没有它工作 agent 只能各自发明译名。

所有轮次完成后：
1. 在 `{{WIKI_ROOT}}/INDEX.md` 末尾追加「如何更新本 wiki」小节，含 marker `<!-- repo-wiki-managed -->`
2. 写 `{{WIKI_ROOT}}/HOW-TO-UPDATE.md`（独立文件）
3. 在 `.wiki-meta/index.json` 的 `_comment` 字段写明常用命令；`last_synced_commit` 写 `git rev-parse HEAD` 的完整 40 位 hash，写 `HEAD` 会让后续所有增量更新的 diff 恒为空
4. 运行验证脚本（见「最终验证规范」节）

---

## Agent Prompt 规范

调度器派发工作 agent 前 Read `$SKILL_ROOT/references/agent-prompt-spec.md` 获取完整 7 节 prompt 结构模板（含源码引用格式 `{{MODULE_ROOT}}/path:L起-L终`、fork delta 标注、补读待办化协议）。

源码引用一律写从项目根起的完整相对路径加行号（`electron/main.js:L45-L60`），不要只写文件名（`main.js:L45`）：增量更新靠这条路径反向映射到页面，文件名在 monorepo 里不唯一，映射就会失效。

以下两个规范块**必须原文复制**到每个工作 agent prompt 的对应节：

### 逐页处理规则（防看门狗超时，必须原文复制到每个 agent prompt）

```
⚠️ 工作模式（极重要）
逐页处理，写完一页立即存盘再处理下一页。
每页顺序：只读该页所需源码（2-5 个文件）→ 生成内容 → 写文件 → 下一页
绝对不要在写任何内容之前读取多个页面的源码。
```

**为什么有这条约束**：主流 AI agent 执行环境通常对工作 agent 设置了输出流看门狗（watchdog）：当工作 agent 在固定时长内没有产生任何输出（包括工具调用反馈），调度器会主动终止它（错误形如 `stalled: no progress for N seconds`）。Claude Code 中此阈值为 600 秒。

### Mermaid 规范（必须原文复制到每个 agent prompt）

```
⚠️ Mermaid 规范（严格遵守）
1. 严禁在节点标签中出现 \n（反斜杠+字母n）— 这在 mermaid 中是字面文字不是换行
2. flowchart/classDiagram 节点换行：用 <br/> 标签，如 A["第一行<br/>第二行"]
3. timeline 类型多行：用 ": 第二行" 续行语法，每行 ≤12 汉字
4. 节点标签使用英文，≤15 字，避免文字溢出
5. 概念型/混合型页面每页 ≥1 个 mermaid 图
6. 若 mermaid 被禁用（run_config.mermaid_enabled = false），改用 ASCII 关系图或省略图表段
```

---

## 模板复用矩阵

不新增模板，通过字段重映射让四种模板适配更多场景（CLI 命令手册、接口契约、配置文件、业务流程、数据模型、注册表、ADR、术语表、章节 README 等）。派发工作 agent 前 Read `$SKILL_ROOT/references/template-reuse-matrix.md`，把对应场景的重映射写进 prompt 的「输出格式」节。

**页面类型选择**：

| 章节类型 | 模板 | 关键要求 |
|---|---|---|
| 架构 / 机制 | `conceptual.md` | ≥1 mermaid，5 段结构 |
| 带丰富 API 的实体 | `mixed.md` | 5 段：定位→动机→机制→API 表→维护要点 |
| API / 配置参考 | `reference.md` | 速查表 + 每实体：签名/参数/行为/示例/源码 |
| 重大决策记录 | `decision-log.md` | 4 段：意图/改动入口/风险与回归点/查看实现 |

---

## 最终验证规范

验证轮（最后一轮，单线程）运行以下脚本：

```bash
python3 $SKILL_ROOT/scripts/check-dead-links.py --wiki-root $WIKI_ROOT
python3 $SKILL_ROOT/scripts/check-mermaid.py --wiki-root $WIKI_ROOT
python3 $SKILL_ROOT/scripts/wiki-stats.py --wiki-root $WIKI_ROOT --min-chars <门槛> --per-page
```

`wiki-stats.py` 的「总页数」已排除 `INDEX.md` / `HOW-TO-UPDATE.md` / `GLOSSARY.md` 与章节 `README.md`，可直接与 schema 的 `target_pages` 比较。

**验证通过标准**：

- [ ] 实际生成页数 ≥ D3 目标值（schema `target_pages`）的 **95%**（`wiki-stats.py` 的总页数含章节 README 与 GLOSSARY，比对前先扣除）
- [ ] 每章实际页数与规划差异 ≤ **±20%**（超出章节列出，由用户确认）
- [ ] `.followup.md` 待办条数 ≤ 总页数的 **10%**（超出说明 anchor 调研不足）
- [ ] `GLOSSARY.md` 存在（`wiki-stats.py` 会直接报告）
- [ ] 每个章节 README 都有对应的 `README.json`
- [ ] 死链数 = 0
- [ ] mermaid 块中无字面 `\n`
- [ ] 每页最低字数达标。**门槛按项目规模取**，不是固定 1800：

  | 源文件数 | 门槛（汉字） | 说明 |
  |---|---|---|
  | < 50 | 1200 | 小项目没有那么多可核实的机制，硬套 1800 会逼出注水内容 |
  | 50–300 | 1800 | 默认档 |
  | > 300 | 2200 | 大仓库单页承载的机制更多 |

  决策记录型（ADR）在任何规模下再降 300：它只写动机、变更入口与风险，不重复实现细节。
  **用 `wiki-stats.py --min-chars <门槛> --per-page` 逐页核对**，不要目测——连续两轮评测里首稿全部不达标，各多花了一轮补写。
  注意报告里的两列不是一回事：「汉字」按中日韩表意文字计（门槛看这一列），「非空白」含标点、英文、路径，通常是前者的 2–3 倍。

**工作 agent 卡死（看门狗超时）处理**：检查 crash 前已写出的文件 → 只针对未写出的页重新派 agent → 重启 agent 时把「逐页处理」规则放在 prompt 最显眼处 → 若持续卡死则减少到 3-4 页/agent。

---

## SKILL_ROOT 解析协议

`{{SKILL_ROOT}}` 是 skill 根目录路径占位符。调度器启动时按 5 级 fallback 解析（环境变量 `REPO_WIKI_SKILL_ROOT` → `runtime.json` 缓存 → 常见安装路径 → 平台注入的 base directory → 报错），成功后写入 `{{WIKI_ROOT}}/.wiki-meta/runtime.json`（git-ignored），下次启动直接命中。完整协议与 `runtime.json` 字段见 `$SKILL_ROOT/references/skill-root-protocol.md`。

---

## .wiki-meta/ Schema 定义

schema v2 采用拆文件结构：`index.json`（顶层元信息）+ `pages/<受众>/<NN-章>/<NN-页>.json`（每页的 `source_files` / `page_type` / `template_version` / `status` / `content_sha256_normalized`）+ `runtime.json`（运行时缓存，git-ignored）。v2.0 的扁平 `pages/{chapter}/{page}.json` 仍可读取，无需迁移。

写入或校验元数据前 Read `$SKILL_ROOT/references/meta-schema-fields.md`（字段速查、常见错误如把 `HEAD` 写进 `last_synced_commit`、把目录写进 `source_files`）；JSON Schema 本体见 `$SKILL_ROOT/references/meta-schema.json`，脚本侧由 `scripts/delta-schema.py` 执行校验。

---

## 兼容矩阵

```
skill v2.0.x  ⇄  schema v2    ⇄  template v2.x.y
skill v2.1.x  ⇄  schema v2.1  ⇄  template v2.x.y（不变）
```

schema 升级时（major 版本变更），必须：在 CHANGELOG.md 中写明不兼容变更 + 提供迁移脚本 `scripts/migrate-meta.py --from-version N --to-version M` + 更新此兼容矩阵。

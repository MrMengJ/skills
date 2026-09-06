<!-- template-version: 2 -->
# 决策点 D1–D5 完整 UI 文本

调度器在 Phase 0 调研完成后 Read 本文件，获取每个决策点的完整展示文本。

**所有决策点 prompt 末尾必须附加**：
`[ ? 查看说明 | back 回上步 | skip-all 全部默认 | edit-schema 直接改 .wiki-meta | cancel 取消 ]`

主流程必须识别这些元命令而非把它们当作选项内容（`?` 展示说明、`back` 回上步、`skip-all` 全部取默认值、`edit-schema` 直接开放 schema 编辑、`cancel` 退出）。

---

## Tier 1 工具绑定（按平台）

调度器在能力探测通过后，以下平台使用对应工具实现决策点：

| 平台 | 结构化交互工具 | 适用 Tier |
|---|---|---|
| Claude Code（CLI / IDE / web） | `AskUserQuestion` | **Tier 1** |
| Cursor / Cline / Continue / Aider / Codex CLI / Gemini CLI | （无等价工具） | Tier 2 |
| 任意 stdin 环境（无 agent） | `scripts/upgrade-cli.py` | Tier 3 |

调度器优先按能力探测结果（尝试调用 → 成功/失败）选 Tier，上表仅作 fallback 参考。用户可通过 `--platform=tier1/tier2/tier3` 强制指定。

**Tier 1 实现规则**：D1.1 / D1.2 / D2 / D4 / D5 / C1 均用 `AskUserQuestion` 呈现（单选用 `type: select`，多选用 `type: multi_select`）；D3 因含自由文本编辑路径（选项 c）必须降级到文本路径（见下方 D3 状态转移表）。

---

## D1 受众（两步问）

**D1.1 首要受众（单选）**：

```
这份 wiki 的【首要】读者是谁？
(a) 维护者 / 贡献者（预计 20-40 页，含架构分析、机制深探、调试指南）
(b) 使用者 / 集成方（预计 15-25 页，含 API 参考、配置手册、快速开始）
(c) 新人 / 学习者（预计 20-35 页，含概念解释、上手教程、关键流程图解）
(d) 业务方 / 产品方（预计 10-20 页，含业务流程、功能地图、决策边界）
[ ? 查看说明 | skip-all 全部默认 | cancel 取消 ]
```

**D1.2 次要受众（多选 / 跳过）**：

```
需要为以下次要读者补充入门章节吗？（多选，直接回车跳过）
□ 使用者（补充 API 速查）
□ 新人（补充概念术语表）
□ 业务方（补充功能说明）
[ back 回上步 | skip 跳过 | cancel 取消 ]
```

受众选择写入 schema 的 `audience.primary` / `audience.secondary`。

---

## D2 输出语言

```
wiki 用什么语言写？
(a) 中文
(b) 英文
(c) 跟随项目主语言（自动检测 README + 注释主语言）
[ back | skip-all 全部默认 | cancel ]
```

写入 schema `output_language`。用户级偏好（`~/.repo-wiki/user-preferences.json` 中的 `default_output_language`）作为本题默认值。

---

## D3 章节规划草稿确认

调度器基于 Phase 0 调研结果和「章节规划方法论」产出草稿，**按受众目录分组展示**（每组先列受众目录名，再展开各章）。**章节编号在各受众目录内独立，从 01 开始，不跨受众目录连续**。

**三层结构 Preview 示例**（以维护者+使用者双受众为例）：

```
章节草稿如下：

维护者指南/         ← 受众目录（全中文）
  01-项目全景/       (5p，conceptual)
  02-代码结构与分发机制/ (4p，mixed)
  03-upgrade基线同步全流程/ (6p，mixed)
  04-upgrade二开差异比对算法/ (5p，mixed)
  05-Git历史清理机制/ (4p，mixed)
  06-LicenseKey更新流程/ (3p，mixed)
  07-变更日志生成/   (4p，mixed)
  08-配置管理与环境依赖/ (3p，reference)
  09-常见问题与调试指南/ (3p，conceptual)

使用者指南/         ← 受众目录（编号重新从 01 开始）
  01-子命令速查手册/ (4p，reference)
  02-配置文件说明/   (2p，reference)

您想：
(a) 全部接受，开始生成
(b) 逐章调整（保留 / 删除 / 重命名 / 合并）
(c) 我直接给你修改后的章节列表（自由文本）
(d) 重新调研后再规划（重跑 Phase 0）
[ ? | back | skip-all 全部默认 | cancel ]
```

### D3 状态转移表

| 用户选择 | 含义 | 调度器行为 | 下一步 |
|---|---|---|---|
| **(a)** 全部接受 | 草稿无需改动 | 直接写入 `.wiki-meta/index.json` 的 `chapters[]` | → D4 |
| **(b)** 逐章调整 | 改某些章节的名字/页数/类型 | Tier 1 弹多选"选要调整的章节"；Tier 2 提示"输入章节编号列表（逗号分隔）"；逐章追问字段后写入 | 全部完成 → D4 |
| **(c)** 自由文本编辑 | 手动写 chapters 清单 | 打开系统编辑器让用户改 `.wiki-meta/chapters-draft.yaml`，保存后解析回写；**Tier 1 也必须走文本路径**（此选项含编辑器交互，无法用结构化工具实现） | 解析成功 → D4；失败 → 回 D3 |
| **(d)** 重新调研 | 草稿严重偏题 | 清空调研缓存，跳回 Phase 0 静默调研段 | 重新走 D1 → D3 |

选 (c) 时用户贴修改后清单，调度器重新解析并**二次复述给用户确认**。

fork 决策日志作为草稿中的一章呈现（不单独询问），类型标为 `decision-log`（fork 项目）或 `adr`（非 fork 项目）。

---

## D4 输出目录

（此时用户已看到章节体量，选择更理性。）

```
wiki 输出到哪个目录？
(a) ./wiki/（推荐）
(b) ./docs/wiki/
(c) ./.wiki/（隐藏目录）
(d) 自定义（请输入路径）
[ back | skip-all | cancel ]
```

选定目录写入 schema `wiki_root`。全文用占位符 `{{WIKI_ROOT}}` 指代，执行时替换为绝对路径。

---

## D5 Mermaid 图表

```
是否启用 mermaid 图？
(a) 启用（默认，概念/混合型页面各 ≥1 个）
(b) 仅在概念/混合型页面启用（保守）
(c) 完全禁用（适合在 Confluence / 不支持 mermaid 的平台发布）
[ back | skip-all | cancel ]
```

写入 schema `run_config.mermaid_enabled`，用户级偏好（`default_mermaid_enabled`）作为默认值。

---

## C1 首轮后追问（第一轮生成结束后触发，不在 Phase 0 内）

打印第一轮产出报告卡后追问：

```
📊 第 1 轮产出
  生成 {N} 页（共计 {X} 字，{M} 个 mermaid 图）
  引用源码文件 {K} 个
  下一轮预计生成：{description}

继续模式：
(a) 继续每轮结束暂停（默认，安全）
(b) 直接跑完不暂停
(c) 仅在风险点暂停（如重大决策章节生成前）
```

用户选择写入 `run_config.pause_between_rounds`，下次增量更新沿用。

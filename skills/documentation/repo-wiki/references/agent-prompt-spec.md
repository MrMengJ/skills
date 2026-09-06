<!-- template-version: 2 -->
# 工作 Agent Prompt 规范（完整版）

调度器在派发工作 agent 前 Read 本文件获取完整 prompt 结构模板。

---

## Prompt 结构模板（7 节，顺序固定）

```
## 项目背景
[项目名称、是否 fork、根目录、primary_type、输出语言]

## ⚠️ 工作模式（极重要）
[逐页处理规则 — 从 SKILL.md「逐页处理规则」节原文复制]

## 任务
[输出目录，本 agent 负责的页面列表（必须给出三层绝对路径，不要只写文件名）]

示例：
```
本 agent 负责以下页面（均使用绝对路径，不要简写）：
- /path/to/.repo-wiki/维护者指南/05-Git历史清理机制/01-应用场景与整体流程.md
- /path/to/.repo-wiki/维护者指南/05-Git历史清理机制/02-BFG历史清理操作详解.md
- /path/to/.repo-wiki/维护者指南/05-Git历史清理机制/03-双remote推送与仓库迁移.md
- /path/to/.repo-wiki/维护者指南/05-Git历史清理机制/04-support资源文件复制.md
另外写一份本章 README.md：/path/to/.repo-wiki/维护者指南/05-Git历史清理机制/README.md
```

## 各页面主题与源码锚点
[每页：主题描述 + "仅读这些文件：" 列出 2-5 个绝对路径]

## 输出格式
[页面类型（conceptual / reference / mixed / decision-log）及对应模板要点]

## ⚠️ Mermaid 规范
[从 SKILL.md「Mermaid 规范」节原文复制]

## 代码引用 / Fork 改动 / 字数要求
[源码引用格式 / fork delta 标注（仅 fork 项目）/ 最低字数]
```

---

## 源码引用格式

```
{{MODULE_ROOT}}/path/to/file.ts:L起始行-L结束行
```

占位符说明：
- `{{MODULE_ROOT}}`：当前处理模块的根目录（monorepo 中为具体 package 路径，单体项目为项目根）
- `{{INTERFACE_DEFS}}`：IDL 文件路径（REST/RPC 项目）
- `{{ENTRY_POINTS}}`：项目入口文件列表

**禁止伪造行号**：工作 agent 必须先读文件再引用行号，从不凭空编造。

**primary source 只写具体文件**：写目录（如 `docs/` 或 `.agents/notes`）会让该页在增量更新时永远不被判为受影响，`validate` 会报 `source_is_directory`。supporting 写目录可以接受（「仓库结构与目录地图」这类页面），但那条路径不会产生任何提示。

**页面 sha256 由调度器统一用 `scripts/delta-conflicts.py hash --file <页.md>` 计算后写入 schema**，工作 agent 不要自行实现 normalize。

---

## 页面输出路径格式（v2.1+ 三层结构，强制）

```
{{WIKI_ROOT}}/<audience_dir>/<NN-chapter_dir>/<NN-page_file>.md
```

规则：
- `audience_dir`：全中文受众目录名，如「维护者指南」「使用者指南」
- `NN-chapter_dir`：章节目录，编号在**受众目录内独立**从 01 开始（不跨受众连续），如 `01-项目全景`、`05-Git历史清理机制`
- `NN-page_file`：章内序号（两位数）+ 中文文件名

**示例**（project-upgrade-tool）：
- `.repo-wiki/维护者指南/05-Git历史清理机制/01-应用场景与整体流程.md`
- `.repo-wiki/使用者指南/01-子命令速查手册/01-upgrade命令速查.md`

调度器派发工作 agent 时必须以**绝对路径**给定 output_path，禁止只给文件名或扁平路径。

---

## Fork Delta 标注（仅 fork 项目）

```
🔧 fork 改动 {commit_hash} — {改动说明}
```

使用 `git log --oneline <file>` 获取真实 commit hash。非 fork 项目的 agent prompt 不包含此节。

---

## 补读待办化（防竞态）

工作 agent 完成一页后**自检**：本页所述机制是否每条都能在引用文件中找到对应行号？

- 找不到时，最多补读 1 个文件（补读前必须先把当前草稿存盘）
- 若仍需更多源码，**不再原地读**，改为把缺失内容追加到 `.followup-<agent-id>.md`：

```markdown
## 页面：维护者指南/05-注册表系统/04-Connector连接器.md
- [ ] 缺少 jumpover 算法实现的行号引用（疑似在 packages/x6/src/registry/connector/jumpover.ts 第 30-80 行）
- [ ] 缺少 Connector 接口定义的 TypeScript 类型
```

主流程在每轮结束后合并所有 `.followup-<id>.md` 到 `.followup.md`，然后删除临时文件。验证轮扫描 `.followup.md`，统一处理或提示用户。

---

## 增量更新模式子 Agent 额外指令

当 Δ.7 派发增量重写 agent 时，在「任务」节前额外注入：

```
## ⚠️ 增量更新模式
这是增量更新，不是从头重写。
旧版本摘要：[旧内容关键段落]
改动 commits：[commit list]
要求：保留未变动的结构段落，只重写受源码改动影响的内容段。
```

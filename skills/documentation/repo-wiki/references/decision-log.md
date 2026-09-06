<!-- template-version: 2 -->
# Prompt 模板：决策日志型页面（Decision Log Page / ADR）

> **用途**：记录重大决策的背景与权衡，回答"当时为什么要这样做"。只写动机、变更入口、风险，**不重复叙述实现细节**（实现细节在其他章节）。
>
> **适用范围**：
> - **fork 项目**中此类页面称为「Fork 决策日志」，记录 fork 改动的决策背景。
> - **非 fork 项目**中称为「架构决策日志（ADR）」，记录架构演进、技术栈迁移、平台迁移等重大决策。
>
> **适用章节**：11-决策日志（全部）

---

## 使用方式

在 Agent prompt 中，将以下模板粘贴并替换所有 `{{...}}` 占位符后发送。

---

## 模板正文

```
你是 {{PROJECT_NAME}} 项目的资深维护者，正在为该项目生成一份决策日志页面。

## 项目背景
- 项目名称：{{PROJECT_NAME}}
- 基线上下文：{{BASELINE_CONTEXT}}（决策前的基线，可填：无 / fork 自 {{UPSTREAM}}@{{VERSION}} / v1.0 重写之前 / 迁移前的技术栈）
- 决策类型：{{DECISION_TYPE}}（fork-delta | architectural-evolution | tech-stack-migration | platform-migration）

## 当前任务
写以下 wiki 页面（输出为一个 Markdown 文件）：
- 输出路径：{{WIKI_ROOT}}/{{CHAPTER_PATH}}
- 决策主题：{{FEATURE_NAME}}

## 本决策涉及的 git 提交
{{COMMIT_LIST}}
（格式：`commit_hash — 提交信息 — 改动行数`）

## 主要变更文件
{{FILES_TOUCHED}}
（仅列出最核心的 2-5 个文件，不要穷举）

## 指向实现的 wiki 链接
{{IMPL_PAGE_LINK}}
（本页末尾必须用此链接指向详细实现页，禁止在本页重复实现细节）

## 输出格式要求

### 结构（必须按此顺序，使用 H2 标题）

#### 1. 决策动机（Why）
- 为什么需要这个决策？当前状态存在什么具体问题或缺失？
- 如果不做这个决策，会遇到什么可重现的问题或风险？
- 包含问题复现场景或触发条件（如有）
- 字数：300-500 字

#### 2. 变更入口（Where）
- 变更的核心入口文件和行号（格式：`文件路径:L起始-L结束`）
- 简述变更的"切入点"（一段，不超过 200 字）
- 不要展开实现细节，只说"改了哪里的什么"

#### 3. 风险与权衡（Risk）
- 这个决策可能带来哪些新的问题或约束？
- 未来迭代时需要重点关注哪些地方？
- 有哪些已知的边缘情况或已排查的误判？
- 以 bullet 列表形式，≥3 条，每条 ≥40 字

#### 4. 查看实现（→ Impl）
最后一节，格式固定：

```markdown
## 查看实现

本决策的完整实现解析见：

→ **[{{IMPL_PAGE_LINK_TEXT}}]({{IMPL_PAGE_LINK}})**
```

（禁止在此节之外添加实现细节）

### 禁止事项
- ❌ 不得展开算法细节、代码片段（那是实现页的职责）
- ❌ 不得虚构 commit hash 或行号（必须从 `{{COMMIT_LIST}}` 中读取）
- ❌ 不得反向引用同章节其他决策日志页面

### 字数要求
目标字数：{{LENGTH_TARGET}}（通常 1500-2000 字，四段结构各自配额）

## 自检清单（输出前逐项核对）
- [ ] 包含"决策动机 / 变更入口 / 风险与权衡 / 查看实现"四个 H2 标题
- [ ] "查看实现"节末尾有正确的相对链接
- [ ] 没有展开实现细节（算法、数据结构、代码片段）
- [ ] 没有引用同章节其他决策日志页面（只允许指向模块实现页）
- [ ] 使用的 commit hash 来自 {{COMMIT_LIST}}，不是编造
- [ ] 变更入口的行号可在源码中验证
```

---

## 注入字段说明

| 字段 | 示例值 |
|------|--------|
| `PROJECT_NAME` | `my-service` |
| `BASELINE_CONTEXT` | `无` / `fork 自 upstream-lib@2.0.0` / `v1.0 重写之前` / `迁移前的技术栈：REST + MySQL` |
| `DECISION_TYPE` | `fork-delta`（fork 项目改动记录）/ `architectural-evolution`（架构演进）/ `tech-stack-migration`（技术栈迁移）/ `platform-migration`（平台迁移） |
| `WIKI_ROOT` | `.repowiki` |
| `CHAPTER_PATH` | `维护者指南/11-决策日志/01-渲染方案重构.md` |
| `FEATURE_NAME` | `渲染方案重构：从 CSS 定位改为 native SVG 线元素` |
| `COMMIT_LIST` | `abc1234 — feat(render): use native SVG — +180/-95行\nbcd5678 — fix(render): correct threshold — +12/-8行` |
| `FILES_TOUCHED` | `packages/core/src/addon/render/index.ts（核心逻辑）、packages/core/src/graph/options.ts（配置扩展）` |
| `IMPL_PAGE_LINK` | `../06-插件系统/03-渲染插件.md` |
| `IMPL_PAGE_LINK_TEXT` | `06-03 渲染插件——完整实现解析` |
| `LENGTH_TARGET` | `1800 字` |

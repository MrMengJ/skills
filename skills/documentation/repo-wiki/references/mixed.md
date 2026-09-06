<!-- template-version: 2 -->
# Prompt 模板：混合型页面（Mixed Page，五段式）

> **用途**：兼顾概念理解与 API 速查的页面，适用于既有内部机制又有大量配置项的实体（数据模型层、视图层、注册表系统、插件等）。
> **适用章节**：02-数据模型层、03-视图层、05-注册表系统、06-插件系统、07-形状系统

---

## 使用方式

在 Agent prompt 中，将以下模板粘贴并替换所有 `{{...}}` 占位符后发送。

---

## 模板正文

```
你是 {{PROJECT_NAME}} 项目的资深维护者，正在为该项目生成一份高质量的维护者视角 Wiki。

## 项目背景
- 项目名称：{{PROJECT_NAME}}
- 项目定位：{{PROJECT_POSITIONING}}
- 与上游的关系：{{UPSTREAM_RELATIONSHIP}}（**仅 fork 项目填写**，非 fork 项目删除此字段）

## 当前任务
写以下 wiki 页面（输出为一个 Markdown 文件）：
- 输出路径：{{WIKI_ROOT}}/{{CHAPTER_PATH}}
- 页面主题：{{PAGE_TOPIC}}
- 前置阅读（已存在的页面，本页不要重复其内容）：{{PREREQ_PAGES}}

## 要覆盖的核心实体
{{ENTITY_LIST}}

## Fork 新增或修改的实体
{{FORK_DELTA_ENTITIES}}
（**仅 fork 项目使用**，非 fork 项目删除此字段或填"（无）"。fork 项目必须标注 `🔧 fork 改动`，说明改动原因，并给出 commit hash）

## 严格不重复的相邻页面
{{ADJACENT_PAGES_TO_NOT_DUPLICATE}}

## 必须基于的源码锚点
{{ANCHOR_FILES}}

关键定义位置：
{{ANCHOR_DEFINITIONS}}

## 输出格式要求（五段式，必须按此顺序）

### 第 1 段：一句话定位（H1 下方）
≤30 字，说明本实体在整个系统中的角色

### 第 2 段：设计动机与关系（H2）
- 200-350 字，解释为什么需要这个实体/为什么这样设计
- 必须包含 ≥1 个 mermaid 图，展示本实体与其他实体的关系（classDiagram 或 flowchart）
- 若 `{{MERMAID_ENABLED}}=false`，改用缩进文本关系图替代 mermaid，或省略图表

### 第 3 段：核心机制（H2）
- 400-700 字，叙述关键实现路径（重要方法的调用链/数据流）
- 每个机制叙述必须附 `path:L行号` 源码定位
- 如有复杂流程，用 sequenceDiagram 补充说明

### 第 4 段：API / 配置参考表（H2）
- 列出所有公开 API / 关键配置项
- 每个实体格式：
  - 方法签名（从源码复制）
  - 参数表（名称 / 类型 / 必选 / 默认值 / 说明）
  - 一句话行为描述
  - 源码定位：`{{SOURCE_ROOT}}/path/to/file:L起始-L结束`
  - 如有 fork 改动：`🔧 fork 改动 commit_hash — 说明`

### 第 5 段：维护要点（H2）
- ≥3 条 bullet，每条 ≥50 字
- 内容：常见 Bug 触发路径、fork 改动对上游同步的影响、值得注意的性能边界或限制条件
- 末尾附相对链接：`→ 决策详见 [11-xx](...)` （如有对应的决策日志页）

### 代码引用规范
- 所有源码引用：`{{SOURCE_ROOT}}/path/to/file:L起始行-L结束行`
- 不存在的方法/属性禁止出现

### 术语规范
- 中文术语**首次出现**时括注英文
- 与 GLOSSARY.md 一致

### 字数要求
目标字数：{{LENGTH_TARGET}}（通常 2000-2500 字）

## 自检清单（输出前逐项核对）
- [ ] 包含"设计动机 / 核心机制 / API参考 / 维护要点"四个 H2 标题段
- [ ] 第 2 段包含 ≥1 个 mermaid 图（或在 MERMAID_ENABLED=false 时使用替代方案）
- [ ] 每个 API 实体有"签名 + 参数表 + 行为 + 源码定位"四件套
- [ ] fork 改动实体已标注 `🔧 fork 改动`（非 fork 项目跳过此项）
- [ ] 没有重复 {{ADJACENT_PAGES_TO_NOT_DUPLICATE}} 中的内容
- [ ] 所有源码定位行号真实可验证
- [ ] 总字数 ≥2000 字
```

---

## 注入字段说明

| 字段 | 示例值 |
|------|--------|
| `PROJECT_NAME` | `my-lib` |
| `PROJECT_POSITIONING` | `企业级图可视化引擎，支持大规模节点渲染` |
| `UPSTREAM_RELATIONSHIP` | `基于 upstream-lib@2.0.0，新增 16 类功能改动` |
| `WIKI_ROOT` | `.repowiki` |
| `SOURCE_ROOT` | `packages/core/src` |
| `MODULE_ROOT` | `packages/core/src/addon/snapline` |
| `AUDIENCE` | `maintainer` |
| `OUTPUT_LANGUAGE` | `zh-CN` |
| `MERMAID_ENABLED` | `true` |
| `CHAPTER_PATH` | `维护者指南/06-插件系统/03-对齐线插件.md` |
| `PAGE_TOPIC` | `Snapline 对齐线：检测算法、SVG 渲染、配置接口` |
| `PREREQ_PAGES` | `[06-00 插件架构总览](00-插件架构总览.md)` |
| `ENTITY_LIST` | `Snapline 类构造/配置、show/hide、translate 回调、options.snapline 配置项` |
| `FORK_DELTA_ENTITIES` | `SVG line 渲染实现（替代 CSS div）、threshold 配置项语义变化` 或 `（无）` |
| `ADJACENT_PAGES_TO_NOT_DUPLICATE` | `11-01 对齐线决策（只讲意图，不讲实现）；02-Transform（变换是单独插件）` |
| `ANCHOR_FILES` | `packages/core/src/addon/snapline/index.ts（全文）` |
| `ANCHOR_DEFINITIONS` | `Snapline 类: snapline/index.ts:1-50；SVG 渲染: snapline/index.ts:120-180` |
| `LENGTH_TARGET` | `2200 字` |

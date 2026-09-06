<!-- template-version: 2 -->
# Prompt 模板：概念型页面（Conceptual Page）

> **用途**：面向维护者的机制解析页。读者不是要学"怎么调用"，而是要理解"为什么这样设计"和"内部是怎么工作的"。
> **适用章节**：00-项目全景、01-核心架构机制、09-框架集成、12-示例应用解析

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
- 技术栈概要：{{TOPOLOGY_SUMMARY}}

## 当前任务
写以下 wiki 页面（输出为一个 Markdown 文件）：
- 输出路径：{{WIKI_ROOT}}/{{CHAPTER_PATH}}
- 页面主题：{{PAGE_TOPIC}}
- 前置阅读：{{PREREQ_PAGES}}（这些页面已存在，本页不要重复其内容）

## 本页需要回答的核心问题
{{KEY_QUESTIONS}}

## 严格不重复的相邻页面
{{ADJACENT_PAGES_TO_NOT_DUPLICATE}}
（如发现内容边界不清，在页尾用"→ 参见 [X]"链接，不要内联重复）

## 必须基于的源码锚点
以下文件/行号是本页的事实基础，**所有机制叙述必须能在这些位置找到对应实现**：
{{ANCHOR_FILES}}

关键定义位置：
{{ANCHOR_DEFINITIONS}}

关键调用链：
{{ANCHOR_CALL_CHAINS}}

## 输出格式要求

### 结构（必须按此顺序）
1. **一句话定位**（H1 标题下方，≤30 字，说明本机制在整个系统中的角色）
2. **设计动机**（H2，300-500 字，解释为什么需要这个机制、不用它会发生什么）
3. **核心机制**（H2，叙述 + ≥1 个 mermaid 图，展示数据流或调用序列）
4. **关键边界与陷阱**（H2，bullet 列表，≥3 条，每条 ≥50 字）
5. **与相邻机制的关系**（H2，说明本机制如何与前置/后续机制协作，包含指向相邻页的相对链接）

### 代码引用规范
- 所有源码引用格式：`{{MODULE_ROOT}}/path/to/file:L起始行-L结束行`
- 禁止引用不存在的文件或行号

### 术语规范
- 中文术语**首次出现**时括注英文：如"标志位（FLAG）"
- 术语定义必须与 GLOSSARY.md 一致

### Mermaid 要求
- 概念型页**必须**包含 ≥1 个 mermaid 图
- 推荐类型：flowchart（数据流）、sequenceDiagram（调用序列）、classDiagram（继承关系）
- 每个节点/箭头上的文字必须简洁（≤15 字）
- 若 `{{MERMAID_ENABLED}}=false`，概念型页面改用缩进文本关系图替代 mermaid，或省略图表

### 字数要求
目标字数：{{LENGTH_TARGET}}（通常 1800-2500 中文字符）

## 自检清单（输出前逐项核对）
- [ ] 每个机制叙述都有 `path:L行号` 源码定位
- [ ] 中文术语首次出现括注英文
- [ ] 包含 ≥1 个 mermaid 图（或在 MERMAID_ENABLED=false 时使用替代方案）
- [ ] "关键边界与陷阱"≥3 条，每条实质性内容 ≥50 字
- [ ] 没有引用不存在的相邻页（链接目标已存在）
- [ ] 总字数 ≥1800 字
```

---

## 注入字段说明

| 字段 | 示例值 |
|------|--------|
| `PROJECT_NAME` | `my-lib` |
| `PROJECT_POSITIONING` | `企业级图可视化引擎，支持大规模节点渲染` |
| `UPSTREAM_RELATIONSHIP` | `基于 upstream-lib@2.0.0，新增 10 类功能改动` |
| `TOPOLOGY_SUMMARY` | `TypeScript + SVG，Monorepo（Lerna），8 个包，MVC 架构` |
| `WIKI_ROOT` | `.repowiki` |
| `SOURCE_ROOT` | `packages/core/src` |
| `MODULE_ROOT` | `packages/core/src/view` |
| `AUDIENCE` | `maintainer` |
| `OUTPUT_LANGUAGE` | `zh-CN` |
| `MERMAID_ENABLED` | `true` |
| `CHAPTER_PATH` | `维护者指南/01-核心架构机制/02-调度系统.md` |
| `PREREQ_PAGES` | `[01-00 总览](00-架构总览.md)、[01-01 Store](01-Store属性变更系统.md)` |
| `PAGE_TOPIC` | `FLAG 位运算调度系统：FLAG 分配规则、三级优先队列、rAF 循环` |
| `KEY_QUESTIONS` | `1. FLAG 是什么？为什么用位运算？\n2. 三级队列各自处理什么？优先级如何定？\n3. rAF 如何防止掉帧？` |
| `ADJACENT_PAGES_TO_NOT_DUPLICATE` | `Renderer 详细实现（03-03）；Store 变更触发（01-01）` |
| `ANCHOR_FILES` | `packages/core/src/view/flag.ts、packages/core/src/graph/renderer.ts` |
| `ANCHOR_DEFINITIONS` | `FlagManager: flag.ts:6-103；三级队列: renderer.ts:48-65` |
| `ANCHOR_CALL_CHAINS` | `Cell.setAttrs → Store.mutate → change:* → CellView.onAttrsChange → FLAG 置位 → Renderer 调度` |
| `LENGTH_TARGET` | `2000 字` |

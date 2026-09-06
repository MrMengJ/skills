<!-- template-version: 2 -->
# Prompt 模板：参考型页面（Reference Page）

> **用途**：API / 配置项 / 实体清单的速查手册。读者来这里查"这个参数叫什么名字"、"这个方法的签名是什么"，不是来理解设计的。
> **适用章节**：04-门面层、05-注册表系统（部分）、08-工具函数与基础类型、10-UI组件库、13-工程化与基础设施

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
- 上游参考版本：{{UPSTREAM_REFERENCE}}（可作为基准，但以实际源码为准，以 fork 改动为优先）

## 当前任务
写以下 wiki 页面（输出为一个 Markdown 文件）：
- 输出路径：{{WIKI_ROOT}}/{{CHAPTER_PATH}}
- 页面主题：{{PAGE_TOPIC}}

## 要覆盖的实体列表
{{ENTITY_LIST}}
（每个实体必须有：方法/属性签名 + 参数说明表 + 行为描述 + 最小可运行示例 + fork delta 标注）

## Fork 新增或修改的实体
{{FORK_DELTA_ENTITIES}}
（这些实体必须额外标注 `🔧 fork 改动`，并在说明中描述改动原因）

## 必须基于的源码文件
{{ANCHOR_FILES}}
（所有签名、类型、默认值必须从这些文件中读取，不得编造）

## 接口定义文件（IDL）
{{INTERFACE_DEFS}}
（REST/RPC 项目填写 .proto、openapi.yaml 等 IDL 文件路径；纯库项目填"（无）"）

## 入口文件
{{ENTRY_POINTS}}
（公共 API 入口文件列表，用于确认哪些符号对外可见）

## 输出格式要求

### 结构（必须按此顺序）
1. **章节定位**（H1 下方，≤50 字，说明本页在整个 wiki 中的位置和读者适用场景）
2. **实体速查表**（H2，一张 Markdown 表格，每行：实体名 | 类型 | 一句话说明 | 源码行号）
3. **逐实体详解**（H2，每个实体一个 H3 子节）

### 逐实体 H3 格式（每个实体必须包含这四项）
```
### EntityName

**签名**
\`\`\`语言（根据项目实际语言填写，不强制用 TypeScript）
// 从源码复制，不要简化
\`\`\`

**参数**
| 参数名 | 类型 | 是否必选 | 默认值 | 说明 |
|--------|------|---------|--------|------|

**行为**
（1-3 段文字，说明这个方法/属性做了什么，异常情况下行为是什么）

**示例**
\`\`\`语言
// 最小可运行示例，≤15 行
\`\`\`

**源码定位**
`{{SOURCE_ROOT}}/path/to/file:L起始-L结束`

**fork delta**（仅 fork 改动实体需要）
🔧 `commit hash` — 改动说明
```

### 代码引用规范
- 签名必须从源码复制，不得简化或臆造
- 所有 `源码定位` 格式：`{{SOURCE_ROOT}}/path/to/file:L起始行-L结束行`
- 不存在于实际源码的方法/属性禁止出现

### 术语规范
- 中文术语**首次出现**时括注英文
- 术语定义必须与 GLOSSARY.md 一致

### 字数要求
目标字数：{{LENGTH_TARGET}}（每个实体平均 200-400 字，参考型页面允许字数更灵活）

## 自检清单（输出前逐项核对）
- [ ] 每个实体都有完整的"签名 + 参数表 + 行为 + 示例 + 源码定位"五件套
- [ ] fork 改动实体已标注 `🔧 fork 改动`
- [ ] 所有签名类型/参数名从源码读取，不是编造
- [ ] 源码定位行号可验证（在给定的 ANCHOR_FILES 中真实存在）
- [ ] 速查表已覆盖所有实体
- [ ] 没有遗漏 ENTITY_LIST 中的任何实体
```

---

## 注入字段说明

| 字段 | 示例值 |
|------|--------|
| `PROJECT_NAME` | `my-lib` |
| `PROJECT_POSITIONING` | `企业级图可视化引擎，支持大规模节点渲染` |
| `UPSTREAM_REFERENCE` | `upstream-lib@2.0.0` |
| `WIKI_ROOT` | `.repowiki` |
| `SOURCE_ROOT` | `packages/core/src` |
| `INTERFACE_DEFS` | `proto/service.proto` 或 `（无）` |
| `ENTRY_POINTS` | `packages/core/src/index.ts` |
| `AUDIENCE` | `user` |
| `OUTPUT_LANGUAGE` | `zh-CN` |
| `CHAPTER_PATH` | `维护者指南/04-门面层/06-history.md` |
| `PAGE_TOPIC` | `HistoryManager：撤销/重做、命令批处理、可配置过滤` |
| `ENTITY_LIST` | `undo()、redo()、canUndo()、canRedo()、batch()、on('change:history')、options.history` |
| `FORK_DELTA_ENTITIES` | `（无，本页无 fork 改动）` 或 `options.history.beforeAddCommand（fork 新增的过滤回调）` |
| `ANCHOR_FILES` | `packages/core/src/graph/history.ts（全文）` |
| `LENGTH_TARGET` | `2000 字` |

---

## CLI 手册模式字段映射（当页面描述 CLI 命令时使用）

将「逐实体详解」格式改为：

### <command> [subcommand]

**Synopsis**
```
command [flags] [args]
```

**选项（Options）**
| 标志 | 类型 | 默认值 | 说明 |

**行为**（1-3 段）

**典型用例**
```
# 示例命令
```

**退出码（Exit Codes）**
| 代码 | 含义 |

**相关命令**（link）

**源码定位**
`{{SOURCE_ROOT}}/path/to/command.go:L起始-L结束`

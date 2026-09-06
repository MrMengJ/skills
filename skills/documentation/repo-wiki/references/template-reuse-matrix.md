<!-- template-version: 2 -->
<!-- 重建说明：原件于 2026-09-03 丢失，本文按 SKILL.md「模板复用矩阵」节与四份模板文件重写（2026-09-04）。 -->
# 模板复用矩阵（完整版）

原则：**不新增模板**。四份模板（`conceptual.md` / `reference.md` / `mixed.md` / `decision-log.md`）通过字段重映射覆盖更多页面场景。调度器在 D3 章节草稿中为每章标注模板类型，派发工作 agent 时把本文对应行的「重映射」写进 prompt 的「输出格式」节。

## 页面类型选择

| 章节内容 | 模板 | 关键要求 |
|---|---|---|
| 架构 / 机制 / 数据流 / 生命周期 | `conceptual.md` | ≥1 mermaid，5 段结构：定位 → 动机 → 机制 → 使用 → 误区 |
| 既有内部机制又有大量 API/配置的实体 | `mixed.md` | 5 段：定位 → 动机 → 机制 → API 表 → 维护要点 |
| API / 配置项 / 实体清单速查 | `reference.md` | 速查表 + 每实体：签名 / 参数 / 行为 / 示例 / 源码定位 |
| 重大决策记录（fork / ADR / 迁移） | `decision-log.md` | 4 段：意图 / 改动入口 / 风险与回归点 / 查看实现 |

判断顺序：先问「读者来这页是查还是学」（查 → reference，学 → conceptual），再问「是否两者都要」（→ mixed），最后问「是否在解释一个历史决定」（→ decision-log）。

## 场景重映射

| 场景 | 复用模板 | 字段重映射 | 额外段落 | 可省略 |
|---|---|---|---|---|
| CLI 命令手册页 | `reference.md` | 「方法签名」→「命令 synopsis」；「参数表」→「options（长/短选项、默认值）」；「返回值」→「输出与 exit codes」 | 「exit codes」「相关命令」「典型组合用法」 | 「类型定义」 |
| REST / RPC 接口契约页 | `reference.md` | anchor 改为 IDL（`*.proto` / `openapi*.yaml` / `*.graphql`）；「示例」→「请求 / 响应示例」；「参数表」→「字段表（名称/类型/必填/说明）」 | 「错误码表」「鉴权要求」 | 「源码定位」可改为 IDL 行号 |
| 配置文件参考页 | `reference.md` | 「实体」→「配置节」；「签名」→「YAML/JSON 路径」；「默认值」列必填 | 「环境变量覆盖表」「示例配置全文」 | 「行为」段合并进「说明」 |
| 业务流程页 | `conceptual.md` | mermaid 强制为 `sequenceDiagram` 或 `stateDiagram-v2`；「核心机制」→ 按业务步骤叙述；「误区」→「业务规则与边界条件」 | 「涉及角色 / 系统」 | 「源码定位」（业务方读者不需要） |
| 数据模型 / 表结构页 | `mixed.md` | 「API 表」→「字段表 + 关系（erDiagram）」；「机制」→「生命周期与状态流转」 | 「索引与约束」「迁移历史」 | — |
| 注册表 / 插件系统页 | `mixed.md` | 「API 表」→「内置项清单（名称/用途/来源文件）」；「维护要点」→「如何新增一项」 | 「扩展点契约」 | — |
| ADR / 架构演进页 | `decision-log.md` | `DECISION_TYPE = architectural-evolution`；「上游版本」→「决策前基线」；「fork 改动」→「变更入口」 | 「被否决的备选方案」 | 「上游同步策略」 |
| 技术栈迁移页 | `decision-log.md` | `DECISION_TYPE = tech-stack-migration`；「风险与回归点」→「迁移检查清单」 | 「回滚方案」 | — |
| Fork 决策日志页 | `decision-log.md` | `DECISION_TYPE = fork-delta`；保留全部原字段 | 「上游同步策略」「已知偏离清单」 | — |
| 新人术语表 / 概念页 | `conceptual.md` | 每个术语一小节：定义 → 出现位置 → 相关术语；mermaid 可用 `mindmap` | 「阅读顺序建议」 | 「动机」「误区」可合并 |
| 章节 README（门面页） | `conceptual.md`（精简） | 只保留「定位」+ 本章页面列表（含一句话摘要）+ 阅读顺序 | — | 其余各段 |

## 受众对模板的影响

| 受众 | 偏好模板 | 调整 |
|---|---|---|
| 维护者 | conceptual / mixed | 源码定位必须精确到行号；「误区」段写「改动时容易踩的坑」 |
| 使用者 | reference / mixed | 示例优先；隐藏内部实现细节；「源码定位」可降级为「所在模块」 |
| 新人 | conceptual | 先给心智模型再给细节；每页末尾「下一步读什么」 |
| 业务方 | conceptual（业务流程重映射） | 不出现代码块；mermaid 用 sequence/state；术语用业务语言 |

## 模板版本

四份模板文件头部 `<!-- template-version: N -->`。schema 的 `template_versions` 记录生成时的版本；Phase Δ.6 比对不一致时按 `phase-delta-protocol.md` 的三选一处理。重映射不改变模板版本号。

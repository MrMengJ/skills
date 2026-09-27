# Skills

A collection of reusable [Agent Skills](https://github.com/agentskills/agentskills) for use with Claude Code and other Agent Skills-compatible harnesses.

## Structure

```
skills/
  <category>/
    <skill-name>/
      SKILL.md
```

Each skill directory holds a `SKILL.md` (frontmatter + instructions), optionally alongside `scripts/`, `references/`, `assets/`. Format follows the [Agent Skills spec](https://github.com/agentskills/agentskills).

## Skills

### Design

- **[visual-companion](./skills/design/visual-companion/SKILL.md)**: 从 obra/superpowers 的 brainstorming 抽出的浏览器可视化协作工具：在本地网页里展示方案、收集用户点选，支持多轮迭代。脚本沿用原项目代码（MIT 协议，见目录内 LICENSE）。

### Documentation

- **[repo-wiki](./skills/documentation/repo-wiki/SKILL.md)**: 为任意代码项目生成结构化 wiki，支持 4 类受众（维护者 / 使用者 / 新人 / 业务方）和多种项目形态。

### Memory

- **[agent-memory](./skills/memory/agent-memory/SKILL.md)**: 全局记忆（`~/.agents/memory/`）的维护规范：何时提议、公共还是专属、文件格式与写法要求，写完后用 `~/.agents/sync.sh` 同步到各工具。

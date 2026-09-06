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

### Documentation

- **[repo-wiki](./skills/documentation/repo-wiki/SKILL.md)**: 为任意代码项目生成结构化 wiki，支持 4 类受众（维护者 / 使用者 / 新人 / 业务方）和多种项目形态。

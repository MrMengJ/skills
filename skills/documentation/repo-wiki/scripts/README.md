# scripts/

本目录包含 repo-wiki skill 的辅助脚本。

**运行环境：** Python ≥ 3.8，无第三方依赖（仅用标准库）

| 脚本 | 用途 | 典型调用 |
|---|---|---|
| check-dead-links.py | 扫描 wiki 内死链 | `python3 check-dead-links.py --wiki-root <path>` |
| check-mermaid.py | 检测 mermaid 块中的字面 \n 错误 | `python3 check-mermaid.py --wiki-root <path>` |
| wiki-stats.py | 输出 wiki 统计信息（含逐页字数核对） | `python3 wiki-stats.py --wiki-root <path> [--min-chars 1800] [--per-page]` |
| diff-impact.py | `delta-git.py affected-pages` 的人类可读包装（同样的反向映射，输出给人看而非 JSON） | `python3 diff-impact.py --meta-dir <path> --base <commit>` |
| migrate-meta.py | 迁移 .wiki-meta schema 版本；v1→v2 拆文件（`--meta-file`），v2→v2 就地补缺省字段（`--meta-dir`） | `python3 migrate-meta.py --from-version 1 --to-version 2 --meta-file <path>` |
| skill-self-check.py | 检查 skill 内容 hash 是否与 CHANGELOG 一致 | `python3 skill-self-check.py --skill-root <path>` |
| design-notes-lint.py | 校验 design-notes/ 目录结构 | `python3 design-notes-lint.py --skill-root <path>` |
| docs-drift-helper.py | 展示升级影响的文档文件清单 | `python3 docs-drift-helper.py --skill-root <path>` |
| release-finalize.sh | 执行 skill 升级收尾操作 | `./release-finalize.sh --plan <path> --new-version <ver> --topic-slug <slug>` |
| upgrade-cli.py | --upgrade 的纯 CLI 入口 | `python3 upgrade-cli.py --interactive` |
| delta-git.py | Phase Δ git 操作（预检/diff收集/反向映射/孤儿扫描）；`precheck --base` 复检纠正后的基线，`affected-pages --no-truncate` 取全量，`orphan-scan --since <commit>` 只看新增 | `python3 delta-git.py precheck --meta-dir <path>` |
| delta-conflicts.py | Phase Δ sha256 冲突检测；`hash --file <页.md>` 输出单页 sha256 供 update-page 使用 | `python3 delta-conflicts.py check --meta-dir <path> --wiki-root <path>` |
| delta-schema.py | Phase Δ schema 校验（含拦截符号引用基线）/读写/staging 事务 | `python3 delta-schema.py validate --meta-dir <path>` |
| help.py | 显示 skill 用法（版本号动态读取） | `python3 help.py` |

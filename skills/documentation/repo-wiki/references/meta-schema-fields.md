<!-- template-version: 2 -->
<!-- 说明：本文内容原位于 SKILL.md「.wiki-meta/ Schema 定义」与「SKILL_ROOT 解析协议」节，2026-09-04 v2.1.1 按渐进式披露原则下沉至此。JSON Schema 本体见 meta-schema.json。 -->
# .wiki-meta/ 字段速查与兼容说明

调度器在写入或校验元数据时（首次生成 Phase 2、Phase Δ.-1 / Δ.7 / Δ.9）Read 本文；完整约束以 `meta-schema.json` 为准，脚本侧由 `scripts/delta-schema.py` 执行。

## 目录结构

schema v2 采用拆文件结构：多人并发改不同页时，merge 冲突局限到单页 JSON。

```
{{WIKI_ROOT}}/.wiki-meta/
├── index.json                             ← 顶层元信息（is_fork / last_synced_commit / template_versions / chapters[] 等）
├── pages/
│   └── {audience_dir}/                    ← v2.1+ 三层路径：受众目录
│       └── {NN-chapter_dir}/              ←          章节目录
│           └── {NN-page}.json             ← 每页独立（source_files / page_type / sha256 等）
└── runtime.json                           ← 运行时缓存（git-ignored，不提交）
```

**v2.0 兼容说明**：v2.0 wiki 的 pages/ 路径扁平（`pages/{chapter}/{page}.json`），仍可被 `delta-schema.py` 读取；不需要迁移。v2.1+ 新生成的 wiki 按三层路径写入。章节 `README.md` 也要有对应的 `README.json`（否则 Δ.4 冲突检测会漏掉它）。

## index.json 关键字段

| 字段 | 说明 |
|---|---|
| `schema_version` | 整数，迁移路径判断（`scripts/migrate-meta.py`）；当前 2 |
| `last_synced_commit` | **完整 40 位 hash**，由 `delta-schema.py update-sync` 写入。写 `HEAD`、分支名或短 hash 会让 Phase Δ 的 diff 恒为空；自 v2.1.2 起 `validate` 与 `precheck` 会直接报 `symbolic_base` 拦截 |
| `last_synced_branch` | 分支一致性检查（Phase Δ.1） |
| `primary_type` / `secondary_types` | D1 之前的类型探测结果；影响 `ignore_patterns` 默认值与章节启发式 |
| `audience.primary` / `audience.secondary` | D1.1 / D1.2 |
| `wiki_root` | D4；相对项目根，如 `./.wiki/` |
| `source_root` | 可选，`source_files[].path` 相对于哪个目录，**相对 wiki 根目录解析**。常见布局 `<项目>/.wiki` 对应 `..`（默认）；工作区级 wiki 覆盖多个仓库时可能是 `../..`。不记录它，`validate` 与反向映射就只能靠 `--repo-root` 猜，猜错会把全部源码报成缺失 |
| `template_versions` | 生成时四种模板的版本；Phase Δ.6 比对漂移 |
| `template_upgrade_suppressed_until` | `{ "<template>": "<rejected_version>" }`，抑制模板升级提示 |
| `ignore_patterns` | 孤儿扫描的忽略规则；缺省按 `primary_type` 选默认值（TS/JS/Python/Go/Rust/Java） |
| `chapters[]` | `id` / `title` / `audience_dir` / `chapter_dir` / `type` / `target_pages` / `pages[]` |
| `run_config` | `pause_between_rounds` / `mermaid_enabled` |
| `_comment` | 常用命令提示，供直接打开文件的人阅读 |

## pages/**.json 关键字段

| 字段 | 说明 |
|---|---|
| `source_files[].path` | 从项目根起的相对路径。**primary 必须是具体文件**，写目录会被 `validate` 报 `source_is_directory`（目录不出现在 git diff 的文件列表里，该页将永远不被判为受影响）；supporting 写目录只会进 `notes[]`，不算错误 |
| `source_files[].role` | `primary`（改动触发整页重写）/ `supporting`（仅提示）。2026-07 期间生成的 wiki 写的是 `secondary`，脚本按 `supporting` 兼容并在 `notes[]` 提示，可用 `migrate-meta.py --from-version 2 --to-version 2 --meta-dir <path>` 统一改写 |
| `page_type` | `conceptual` / `reference` / `mixed` / `decision-log` |
| `template_version` | 生成该页时的模板版本 |
| `status` | `active` / `deprecated`（所有 primary 源码已删除） |
| `content_sha256_normalized` | normalize 后的 sha256。**一律用 `delta-conflicts.py hash --file <页.md>` 取值，不要自行实现**：口径差一点点，首次 `--update` 就会把每一页都误判成「手动改动冲突」 |
| `content_sha256_no_whitespace` | 可选。去掉全部空白后的 sha256；写了它，Δ.4 才能把「只重排了空行」和「真改了内容」区分开，否则 `is_whitespace_only` 返回 `null` |
| `anchor_material` / `anchor_commits` | 可选：IDL / schema 等锚点材料与引用的 commit |

## normalize 口径（normalization_protocol_version = v1）

`content_sha256_normalized` 的计算步骤，按顺序：

1. 以 `utf-8-sig` 解码（去掉 BOM）
2. `\r\n` 与 `\r` 全部替换为 `\n`
3. `rstrip("\n")`：去掉**结尾的换行符**，注意不去行尾空格、不去行首空白、不改中间空行
4. 以 `utf-8` 编码后取 sha256

`content_sha256_no_whitespace`（可选）在第 3 步之后再删除全部空白字符，用于判定冲突是否只是空白差异。

这两个值都由 `scripts/delta-conflicts.py hash --file <页.md>` 一次输出。上面的步骤只是让你看懂它在做什么，**实际写入 schema 时请调脚本**：手写实现哪怕只在第 3 步多做一次 `strip()`，算出的 hash 就和脚本对不上，后果是首次增量更新把全部页面误报为冲突。

---

## runtime.json

运行时缓存，git-ignored。字段与 SKILL_ROOT 解析协议见 `skill-root-protocol.md`。

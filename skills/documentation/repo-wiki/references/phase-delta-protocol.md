<!-- template-version: 2 -->
# Phase Δ 增量更新协议（完整版）

调度器在进入 Phase Δ 前 Read 本文件获取详细步骤。

## 脚本调用速查

**exit code 约定**：exit 0 + `"ok": false` = 业务问题（需 Claude 与用户交互决策）；exit 1 = 脚本错误（直接报告）

| 步骤 | 调用 | 关键输出字段 |
|---|---|---|
| Δ.-1 | `python3 $SKILL_ROOT/scripts/delta-schema.py validate --meta-dir {{WIKI_ROOT}}/.wiki-meta/ --repo-root .` | `ok`, `errors[]`, `notes[]`, `staging_residue` |
| Δ.1 | `python3 $SKILL_ROOT/scripts/delta-git.py precheck --meta-dir {{WIKI_ROOT}}/.wiki-meta/` | `ok`, `issues[]` |
| Δ.2 | `python3 $SKILL_ROOT/scripts/delta-git.py collect --base {{LAST_SYNCED_COMMIT}}` | `added`, `modified`, `deleted`, `renamed`, `split_candidates` |
| Δ.3 | `python3 $SKILL_ROOT/scripts/delta-git.py affected-pages --meta-dir {{WIKI_ROOT}}/.wiki-meta/ --base {{LAST_SYNCED_COMMIT}} --no-truncate` | `primary`, `supporting`, `deprecated`, `needs_review`, `counts`, `reasons` |
| Δ.4 | `python3 $SKILL_ROOT/scripts/delta-conflicts.py check --meta-dir {{WIKI_ROOT}}/.wiki-meta/ --wiki-root {{WIKI_ROOT}}` | `ok`, `conflicts[]`, `clean[]` |
| Δ.7 write | `python3 $SKILL_ROOT/scripts/delta-schema.py write-staging --meta-dir {{WIKI_ROOT}}/.wiki-meta/ < <new_index_json>` | `ok`, `staging` |
| Δ.7 commit | `python3 $SKILL_ROOT/scripts/delta-schema.py commit-staging --meta-dir {{WIKI_ROOT}}/.wiki-meta/` | `ok` |
| Δ.7 rollback | `python3 $SKILL_ROOT/scripts/delta-schema.py rollback-staging --meta-dir {{WIKI_ROOT}}/.wiki-meta/` | `ok` |
| Δ.7 page | `python3 $SKILL_ROOT/scripts/delta-schema.py update-page --meta-dir ... --page <rel> --sha256 <hash> --template-version <n>` | `ok`, `changed` |
| Δ.8 | `python3 $SKILL_ROOT/scripts/delta-git.py orphan-scan --meta-dir {{WIKI_ROOT}}/.wiki-meta/ --repo-root . --base {{LAST_SYNCED_COMMIT}} --no-truncate` | `orphans[]`, `clusters[]`, `added_since_base` |
| Δ.9 | `python3 $SKILL_ROOT/scripts/delta-schema.py update-sync --meta-dir {{WIKI_ROOT}}/.wiki-meta/ --commit HEAD --branch <name>` | `ok` |

---

## Δ.-1 schema 校验（必跑，在 Δ.0 之前）

```bash
python3 $SKILL_ROOT/scripts/delta-schema.py validate \
  --meta-dir {{WIKI_ROOT}}/.wiki-meta/ \
  --repo-root .
```

**`--repo-root` 不能省**：省了它就跳过 `source_files` 的存在性检查，下面的 `missing_source_file` 分流永远不会触发，而源码被删改路径恰恰是最常见的 schema 失效原因。

输出 JSON 后，按 `errors[]` 中的 `type` 字段分流：

```
- symbolic_base（options: resolve/specify/rebuild）
  → last_synced_commit 不是完整 40 位 hash（常见于历史产物里的字面量 "HEAD"）。
    此时 base..HEAD 恒为空，任何 diff 结论都不可信，必须先纠正：
    (a) 从 INDEX.md 的「同步基线」或 git reflog 找回真实 hash，用 --from <hash> 继续
    (b) 用户指定起点  (c) 转 --rebuild
    纠正后可用 `delta-git.py precheck --base <hash>` 复检 Δ.1

- notes[] 里出现 source_root_mismatch
  → 绝大多数源码路径都找不到，说明 --repo-root 给错了（工作区级 wiki 的 source_files
    常相对工作区根写）。先换对根重跑 Δ.-1，不要照着 missing_source_file 逐条改数据。

- json_syntax / type_error / missing_field
  → 报告精确错误路径，abort，要求用户手动修复后重跑

- source_is_directory（options: expand/typo/skip）
  → 某页把**目录**写成了 primary 源。目录不出现在 git diff 的文件列表里，
    这一页永远不会被判为受影响，是静默假阴性。让用户把目录展开成该目录下
    真正驱动这一页内容的 1-3 个文件。
    （写成 supporting 的目录不报错，只在 `notes[]` 里提示，「目录地图」类页面这样写是合理的）

    **批量情形**：整份 wiki 都按目录粒度写 primary 源时（模块化 Java / Go 仓库常见，
    一次能报出几十条），不要逐条询问。按页分组汇总展示，给三个整体选项：
    (a) 逐页展开——为每页挑 1-3 个真正驱动内容的文件，工作量大但一劳永逸
    (b) 本次跳过——继续做 diff 分析，但明确告知这些页不会出现在受影响列表里
    (c) 转 --rebuild——重建时按新规范写 source_files
    选 (b) 时必须在最终报告里单列「因 source 粒度问题而未参与判定的页」，
    否则用户会以为这些页真的没受影响。

- missing_source_file（options: renamed/deleted/typo/skip）
  → 对每个不存在的路径询问：
    「(a) 已重命名  (b) 已删除（标 deprecated）  (c) 拼写错误  (d) 跳过」

- schema_version_ahead（action: run_migrate_meta）
  → 提示用户运行 scripts/migrate-meta.py 迁移

- template_version_ahead
  → abort，提示「您的 wiki 由更新版本的 skill 生成，请先升级 skill 再运行更新」

- staging_residue: true
  → 询问：「上次更新中断，是否：(a) 续传 (b) 丢弃 staging 重来 (c) 查看 diff」

全部 ok → 进入 Δ.0
```

---

## Δ.0 参数复述与确认

调度器先用自然语言复述解析结果，再执行。示例：

```
我解析到的意图是：
  模式：增量更新
  范围：05-注册表系统/（相对 {{WIKI_ROOT}}，绝对路径 /path/to/wiki/05-注册表系统/）
  起始 commit：abc123（来自 --from 参数，覆盖 schema 默认值 ecda8dd）
  是否 dry-run：否

确认无误吗？（确认 / 调整范围 / 取消）
[ ? 查看说明 | back 回上步 | skip-all 全部默认 | edit-schema 直接改 .wiki-meta | cancel 取消 ]
```

**取消词典**（全部映射为 cancel，直接 exit，不写任何文件）：
算了 / 不要了 / cancel / 退出 / 等等 / 先不弄了 / 等下

**自由文本修正**：用户用自然语言修改参数，调度器提取后重新复述再确认，最多 3 轮收敛，超出则 abort。

**--from 旧 hash 警告**：若 `--from <hash>` 早于 `last_synced_commit`，显式提示：
```
您指定 --from {hash1}，但上次同步是 {hash2}（hash1 在 hash2 之前）。
这意味着 commits hash1..hash2 之间的改动也会被纳入更新，可能与已有 wiki 状态产生冲突。
是否继续？(yes / no / 先 dry-run 看看)
```
默认走 dry-run。**Δ.0 失败禁止自动 fallback 到 Phase 0**；必须用户明示才能切换。

---

## 符号引用基线的纠正（Δ.-1 报 symbolic_base 后）

三步，缺一不可：

1. **找回真实基线**：`{{WIKI_ROOT}}/INDEX.md` 顶部的「同步基线」通常记着 `分支@短hash`；没有就查 `git reflog` 或用 `git log --before=<generated_at>` 找生成当天的 commit。
2. **展开成完整 hash**：`git rev-parse --verify <短hash>^{commit}` —— 后续所有脚本都要求 40 位，短 hash 会被再次判为 `symbolic_base`。
3. **显式透传**：Δ.1 `precheck --base <hash>`、Δ.2 `collect --base <hash>`、Δ.3 `affected-pages --base <hash>`、Δ.8 `orphan-scan --base <hash>` 都要带上，脚本不会互相记忆。

`--dry-run` 下**不写回** `index.json`，只在报告里写明「真实基线是 X，建议用 `/repo-wiki --update --from X` 修正」；非 dry-run 时在 Δ.9 由 `update-sync` 写入完整 hash。

---

## 非交互模式

与 Phase 0 一致：调用方已在上下文里给全了答案（模式、范围、起始 commit、冲突处理策略），就不再逐项询问，只在 Δ.0 复述一次解析结果并继续；缺失项取默认值并在复述里标出。

---

## dry-run 的边界

`--dry-run` 下 Δ.-1 到 Δ.6 与 Δ.8 照常执行（全部只读），Δ.7 重写与 Δ.9 收尾跳过，不写 `runtime.json`、不写 staging、不碰 wiki 页面。把 Δ.8 纳入 dry-run 是有意的：用户问「这次会改哪些页」时，通常同样关心「有没有新模块还没被覆盖」。

---

## Δ.1 git 状态预检

```bash
python3 $SKILL_ROOT/scripts/delta-git.py precheck \
  --meta-dir {{WIKI_ROOT}}/.wiki-meta/ [--base <纠正后的 hash>]
```

`--base` 用于 Δ.-1 报出 `symbolic_base` 并纠正基线之后复检，不给时读 `index.json`。

按 `issues[]` 中的 `type` 字段分流：

```
- unreachable_commit（options: use_merge_base/full_rebuild/specify_start）
  → 询问「上次同步点不可达，选 (a) 最近共同祖先  (b) 全量重建  (c) 手动指定起点」

- dirty_workdir（options: include/exclude）
  → 询问「工作区有未提交改动，是否纳入本次更新？」

- branch_mismatch
  → 提醒「你切了分支，本次更新可能不在原分支语义下，是否继续？」

- symbolic_base
  → 与 Δ.-1 同源；若 issue 里带 `resolved`，把它作为建议起点复述给用户确认
```

---

## Δ.2 差异收集

```bash
python3 $SKILL_ROOT/scripts/delta-git.py collect \
  --base {{LAST_SYNCED_COMMIT}}
```

输出 JSON 含 `added` / `modified` / `deleted` / `renamed`（含 rename 链）/ `split_candidates`。

按 `split_candidates` 触发人工询问：
「文件 `a.ts` 被拆为 `b.ts` 和 `c.ts`？是否更新本页的 `source_files`？」

---

## Δ.3 反向映射（source → pages）

```bash
python3 $SKILL_ROOT/scripts/delta-git.py affected-pages \
  --meta-dir {{WIKI_ROOT}}/.wiki-meta/ \
  --base {{LAST_SYNCED_COMMIT}} \
  --no-truncate
```

输出四组：`primary`（整页重写候选）/ `supporting`（提示不重写）/ `deprecated`（候选删除）/ `needs_review`（没有任何源码锚点，或 primary 只被删了一部分——这两种情况从前三组里漏掉，必须人看一眼），外加完整计数 `counts` 与 `reasons`（每页命中了哪些路径、什么角色、改动还是删除）。**汇总展示时直接用 `reasons`，不要自己重做反向映射**——连续两轮评测里 agent 都因为拿不到命中原因而重写了一遍映射逻辑。
做汇总展示时直接加 `--no-truncate` 取全量（默认截断到 50 条，是为防止刷屏，不是为分批）；只有在确实要分批派发工作 agent 时才按批处理。

---

## Δ.4 手动改动冲突检测

```bash
python3 $SKILL_ROOT/scripts/delta-conflicts.py check \
  --meta-dir {{WIKI_ROOT}}/.wiki-meta/ \
  --wiki-root {{WIKI_ROOT}}
```

按 `conflicts[]` 逐项询问：
```
`is_whitespace_only` 为 `true` 表示只有空白差异（仅当页面 json 里存有 `content_sha256_no_whitespace` 时才能判定，否则为 `null`，需要人工确认）。

「该页被手动编辑（normalize 后 sha256 不匹配），是否：
 (a) 保留 wiki 中现存版本（跳过本页重写）
 (b) 用新版覆盖
 (c) 输出 .new 文件做 side-by-side diff」
```

---

## Δ.5 汇总展示 + 决策点

把受影响页分四组展示：

```
A 组（primary 命中）：默认重写 — 列出受影响页数与命中原因（取自 `reasons`）
B 组（仅 supporting 命中）：默认仅提示，不重写 — 列出文件名
C 组（manually_edited 冲突）：三选一（见 Δ.4）
D 组（status=deprecated）：询问「保留为历史 / 删除」
E 组（needs_review）：无源码锚点或 primary 部分被删 — 逐页给出原因，请用户补锚点或确认现状
```

总体决策点（四选一）：「全量执行 / 逐组确认 / 仅看 dry-run / 取消」。
**已经是 `--dry-run` 时只剩两项**：「继续看完 Δ.6 / Δ.8 的报告」或「取消」——此时「仅看 dry-run」是空操作，不要把它当成选项列给用户。

`[ ? 查看说明 | back 回上步 | skip-all 全部默认 | edit-schema 直接改 .wiki-meta | cancel 取消 ]`

---

## Δ.6 模板漂移检测

skill 当前的模板版本取自四份模板文件头部的 `<!-- template-version: N -->`（`references/{conceptual,mixed,reference,decision-log}.md`），没有专门的脚本，直接读文件头即可。与 schema 中记录的版本不一致时：

```
本次受影响的这些页使用了旧版模板（template v1，当前 skill 内置 v2）：
  - 维护者指南/05-注册表系统/04-Connector连接器.md
  ...
是否：
  (a) 升级并按新规范刷新这些页（推荐）
  (b) 仅本次抑制（下次再问）
  (c) 永久抑制此模板升级（写入 template_upgrade_suppressed_until）
```

`template_upgrade_suppressed_until` 字段：`{ "<template_name>": "<version_user_rejected>" }`。当 skill 版本 > 抑制版本时，重新询问。

---

## Δ.7 执行重写（write-ahead 事务）

**事务边界**：

```bash
# 写入前：把新版 index.json 内容写到 staging
echo '<new_index_json>' | python3 $SKILL_ROOT/scripts/delta-schema.py write-staging \
  --meta-dir {{WIKI_ROOT}}/.wiki-meta/

# 全部成功后：atomic rename staging → index.json（同时合并 .followup-*.md）
python3 $SKILL_ROOT/scripts/delta-schema.py commit-staging \
  --meta-dir {{WIKI_ROOT}}/.wiki-meta/

# 中途失败时：rollback（保留 staging 文件供 debug）
python3 $SKILL_ROOT/scripts/delta-schema.py rollback-staging \
  --meta-dir {{WIKI_ROOT}}/.wiki-meta/
```

写完一页后更新页面 schema（幂等，字段未变化时自动 skip）：
```bash
python3 $SKILL_ROOT/scripts/delta-schema.py update-page \
  --meta-dir {{WIKI_ROOT}}/.wiki-meta/ \
  --page <chapter>/<page>.json \
  --sha256 <normalized_sha256> \
  --template-version <n>
```

**子 agent prompt 注入**（增量模式，不变）：
「这是增量更新。旧版本片段为 [旧内容摘要]，改动 commits 为 [commit list]，请基于新源码重写本页，保留未变动的结构段落，重写受影响的内容段。」

子 agent 写补读待办到 `.followup-<agent-id>.md`（不直接写 `.followup.md`，防并发竞态）。`commit-staging` 成功后自动合并 `.followup-*.md`。

---

## Δ.8 孤儿扫描

```bash
python3 $SKILL_ROOT/scripts/delta-git.py orphan-scan \
  --meta-dir {{WIKI_ROOT}}/.wiki-meta/ \
  --repo-root . \
  --base {{LAST_SYNCED_COMMIT}} \
  --no-truncate
```

输出 JSON 含 `orphans[]`（未记录的源码文件）和 `clusters[]`（同目录孤儿 ≥5 个时归为一簇）。

默认同样截断到 200 条，汇总展示时加 `--no-truncate` 取全量（与 Δ.3 一致）。`--base` 与 `--since` 是同一个参数的两种写法，推荐用 `--base` 与其他子命令保持一致。

**回答「新出现哪些未覆盖模块」时加 `--base {{LAST_SYNCED_COMMIT}}`**：只保留自基线以来新增的文件，把「这个仓库历来就没覆盖的杂项」和「这次新长出来的模块」区分开。不加时会把全部历史未覆盖文件一起报出来（大仓库可达数千条），淹没真正的新增。脚本按 schema 中 `ignore_patterns` 过滤；若 schema 未设置，按 `primary_type` 自动选用默认值：

| primary_type | 默认 ignore_patterns |
|---|---|
| typescript / javascript | `["*.test.*", "*.spec.*", "*.d.ts", "__mocks__/**", "**/__snapshots__/**", "node_modules/**"]` |
| python | `["**/test_*.py", "**/*_test.py", "**/tests/**", "**/__pycache__/**", "**/conftest.py"]` |
| go | `["**/*_test.go", "**/testdata/**", "**/vendor/**"]` |
| rust | `["**/target/**", "**/tests/**"]` |
| java | `["**/test/**", "**/build/**", "**/target/**"]` |
| 通用兜底（所有项目追加） | `[".git/**", "dist/**", "build/**", "*.log", ".DS_Store"]` |

Claude 据输出做交互决策：
- `ignore_patterns` 展示后询问「需要调整吗？」
- `clusters[]` 非空时提示：「检测到新模块 `{dir}/`（N 个未记录文件），是否新增章节？」

---

## Δ.9 收尾

```bash
python3 $SKILL_ROOT/scripts/delta-schema.py update-sync \
  --meta-dir {{WIKI_ROOT}}/.wiki-meta/ \
  --commit HEAD \
  --branch <当前分支名>
```

输出 `{"ok": true}` 后继续：

```
2. 检查 {{WIKI_ROOT}}/INDEX.md 是否仍含 marker <!-- repo-wiki-managed -->
   （用 Read tool 读文件检查；脚本不处理此项）
   - 被擦除 → 提醒「INDEX.md 中的使用提示已被覆盖，请改看 HOW-TO-UPDATE.md」

3. 打印完成报告：
   「✅ 增量更新完成
      重写页数：N
      跳过页数：M（仅 supporting 命中）
      冲突待处理：K
      .followup.md 待办：P 条
      下次更新：/repo-wiki --update」
```

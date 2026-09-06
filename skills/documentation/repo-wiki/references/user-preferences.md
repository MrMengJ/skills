<!-- template-version: 2 -->
<!-- 重建说明：原件于 2026-09-03 丢失，本文按 SKILL.md / decision-points.md 中对用户级偏好的引用重写（2026-09-04）。 -->
# 用户级偏好（`~/.repo-wiki/user-preferences.json`）

跨项目沿用的默认值。**只影响决策点的默认选项**，不跳过决策点；项目级 schema（`.wiki-meta/index.json`）一旦写入即覆盖用户级偏好。

## 优先级

```
CLI 参数（--platform / --from …）
  > 项目 schema（.wiki-meta/index.json、runtime.json）
    > 用户级偏好（~/.repo-wiki/user-preferences.json）
      > skill 内置默认
```

## 文件格式

```json
{
  "preferences_version": 1,
  "default_output_language": "zh",
  "default_mermaid_enabled": true,
  "default_wiki_root": "./.wiki/",
  "default_pause_between_rounds": "always",
  "default_audience_primary": "maintainer",
  "platform_tier": null,
  "watchdog_seconds": 600
}
```

| 字段 | 影响的决策点 | 取值 | 内置默认 |
|---|---|---|---|
| `default_output_language` | D2 | `zh` / `en` / `follow-project` | `follow-project` |
| `default_mermaid_enabled` | D5 | `true` / `"conceptual-only"` / `false` | `true` |
| `default_wiki_root` | D4 | 相对项目根的路径 | `./wiki/` |
| `default_pause_between_rounds` | C1 | `always` / `never` / `first-time-only` / `risk-points-only` | `always` |
| `default_audience_primary` | D1.1 | `maintainer` / `user` / `newcomer` / `business` | `maintainer` |
| `platform_tier` | 交互执行规范 | `null`（自动探测）/ `1` / `2` / `3` | `null` |
| `watchdog_seconds` | 分轮执行规范 | 正整数 | `600` |

## 读写规则

- 文件不存在 → 静默使用内置默认，**不创建**文件。
- 文件存在但某字段缺失或取值非法 → 该字段回退内置默认，并在开场卡片下方提示一行 `⚠️ user-preferences.json 字段 X 非法，已忽略`。
- 用户在决策点选择了与偏好不同的值时，**不自动回写**偏好；只有用户明确说「以后都这样」（或在决策点输入 `save-default`）才写回。
- 写回时保留未知字段，更新 `preferences_version` 不变（当前 1）。

## 与 schema 字段的对应

| 偏好字段 | 写入 schema 位置 |
|---|---|
| `default_output_language` | `index.output_language` |
| `default_mermaid_enabled` | `index.run_config.mermaid_enabled` |
| `default_wiki_root` | `index.wiki_root` |
| `default_pause_between_rounds` | `index.run_config.pause_between_rounds` |
| `default_audience_primary` | `index.audience.primary` |
| `platform_tier` | `runtime.platform_capabilities.has_structured_input_tool`（仅作探测覆盖，不持久化到 index） |

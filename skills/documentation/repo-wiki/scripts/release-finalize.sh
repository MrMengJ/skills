#!/usr/bin/env bash
# repo-wiki skill 升级收尾固定段（8 步）的单一可信源。
#
# 用法：
#   release-finalize.sh --plan <plan.md> --new-version <ver> --topic-slug <slug> [--skill-root <path>] [--commit] [--summary "<一句话>"]
#   release-finalize.sh --recover [--skill-root <path>]      # 只补 hash / CHANGELOG / design-notes 元数据（步骤 4-6）
#
# 步骤：
#   1. 拷贝 plan → design-notes/v<ver>-<slug>.md
#   2. 更新 design-notes/INDEX.md
#   3. 更新 SKILL.md 顶部 <!-- skill-version: <ver> -->
#   4. 重算 content-hash，更新 CHANGELOG.md 顶部 <!-- skill-content-hash: ... -->
#   5. 在 CHANGELOG.md 写新版本条目（已存在则跳过）
#   6. 运行 design-notes-lint.py + skill-self-check.py
#   7. 用户文档审查（docs-drift-helper.py）
#   8. （可选，--commit）git add -A && git commit
set -euo pipefail

PLAN="" ; NEW_VERSION="" ; SLUG="" ; SKILL_ROOT="" ; DO_COMMIT=0 ; RECOVER=0 ; SUMMARY=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --plan) PLAN="$2"; shift 2 ;;
    --new-version) NEW_VERSION="$2"; shift 2 ;;
    --topic-slug) SLUG="$2"; shift 2 ;;
    --skill-root) SKILL_ROOT="$2"; shift 2 ;;
    --summary) SUMMARY="$2"; shift 2 ;;
    --commit) DO_COMMIT=1; shift ;;
    --recover) RECOVER=1; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "未知参数: $1" >&2; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="${SKILL_ROOT:-$(dirname "$SCRIPT_DIR")}"
SKILL_ROOT="$(cd "$SKILL_ROOT" && pwd)"
SKILL_MD="$SKILL_ROOT/SKILL.md"
CHANGELOG="$SKILL_ROOT/CHANGELOG.md"
NOTES_DIR="$SKILL_ROOT/design-notes"
TODAY="$(date +%Y-%m-%d)"

[[ -f "$SKILL_MD" ]] || { echo "SKILL.md 不存在: $SKILL_MD" >&2; exit 1; }
mkdir -p "$NOTES_DIR"
[[ -f "$NOTES_DIR/INDEX.md" ]] || printf '# design-notes 索引\n\n| 版本 | 主题 | 文件 | 日期 |\n|---|---|---|---|\n' > "$NOTES_DIR/INDEX.md"
[[ -f "$CHANGELOG" ]] || printf '<!-- skill-content-hash: 0000000000000000 -->\n# Changelog\n\nAll notable changes to the `repo-wiki` skill will be documented in this file.\n' > "$CHANGELOG"

if [[ $RECOVER -eq 0 ]]; then
  [[ -n "$PLAN" && -n "$NEW_VERSION" && -n "$SLUG" ]] || { echo "需要 --plan --new-version --topic-slug（或 --recover）" >&2; exit 1; }
  [[ -f "$PLAN" ]] || { echo "plan 文件不存在: $PLAN" >&2; exit 1; }
  [[ "$SLUG" =~ ^[a-z0-9][a-z0-9-]*$ ]] || { echo "topic-slug 只能含小写字母/数字/连字符: $SLUG" >&2; exit 1; }
  NOTE="$NOTES_DIR/v${NEW_VERSION}-${SLUG}.md"

  echo "[1/8] 拷贝 plan → ${NOTE#$SKILL_ROOT/}"
  cp "$PLAN" "$NOTE"

  echo "[2/8] 更新 design-notes/INDEX.md"
  if ! grep -q "v${NEW_VERSION}-${SLUG}.md" "$NOTES_DIR/INDEX.md"; then
    printf '| %s | %s | [%s](%s) | %s |\n' "$NEW_VERSION" "$SLUG" "v${NEW_VERSION}-${SLUG}.md" "v${NEW_VERSION}-${SLUG}.md" "$TODAY" >> "$NOTES_DIR/INDEX.md"
  fi

  echo "[3/8] 更新 SKILL.md 版本号 → $NEW_VERSION"
  NEW_VERSION="$NEW_VERSION" python3 - "$SKILL_MD" <<'PY'
import os, re, sys
p = sys.argv[1]; v = os.environ["NEW_VERSION"]
t = open(p, encoding="utf-8").read()
t2, n = re.subn(r"<!--\s*skill-version:\s*[^>]*-->", f"<!-- skill-version: {v} -->", t, count=1)
if n == 0:
    sys.exit("SKILL.md 缺少 <!-- skill-version: ... --> 行")
t2 = re.sub(r"(# Repo Wiki Generator v)[0-9A-Za-z.\-]+", r"\g<1>" + v, t2, count=1)
t2 = re.sub(r"(🪄 /repo-wiki v)[0-9A-Za-z.\-]+", r"\g<1>" + v, t2, count=1)
open(p, "w", encoding="utf-8").write(t2)
PY
else
  echo "[1-3/8] --recover：跳过 plan / INDEX / 版本号步骤"
  NEW_VERSION="$(sed -nE 's/.*<!-- *skill-version: *([^ >]+) *-->.*/\1/p' "$SKILL_MD" | head -1)"
  SLUG="recover"
fi

echo "[4/8] 重算 content-hash 并写入 CHANGELOG.md 顶部"
HASH="$(python3 "$SCRIPT_DIR/skill-self-check.py" --skill-root "$SKILL_ROOT" --print-hash)"
HASH="$HASH" python3 - "$CHANGELOG" <<'PY'
import os, re, sys
p = sys.argv[1]; h = os.environ["HASH"]
t = open(p, encoding="utf-8").read()
t2, n = re.subn(r"<!--\s*skill-content-hash:\s*[^>]*-->", f"<!-- skill-content-hash: {h} -->", t, count=1)
if n == 0:
    t2 = f"<!-- skill-content-hash: {h} -->\n" + t
open(p, "w", encoding="utf-8").write(t2)
print(f"      hash = {h}")
PY

echo "[5/8] CHANGELOG.md 写入 v${NEW_VERSION} 条目（已存在则跳过）"
NEW_VERSION="$NEW_VERSION" SLUG="$SLUG" TODAY="$TODAY" SUMMARY="$SUMMARY" python3 - "$CHANGELOG" <<'PY'
import os, re, sys
p = sys.argv[1]; v = os.environ["NEW_VERSION"]; slug = os.environ["SLUG"]; today = os.environ["TODAY"]; summary = os.environ.get("SUMMARY", "")
t = open(p, encoding="utf-8").read()
if re.search(r"^##\s*\[" + re.escape(v) + r"\]", t, re.M):
    print(f"      v{v} 条目已存在，跳过")
    sys.exit(0)
entry = f"## [{v}] - {today}\n### Changed\n- {summary or ('升级主题：' + slug + '（详见 design-notes/v' + v + '-' + slug + '.md）')}\n\n"
m = re.search(r"^##\s*\[", t, re.M)
t = (t[:m.start()] + entry + t[m.start():]) if m else (t.rstrip("\n") + "\n\n" + entry)
open(p, "w", encoding="utf-8").write(t)
PY

echo "[6/8] 自检"
python3 "$SCRIPT_DIR/design-notes-lint.py" --skill-root "$SKILL_ROOT"
python3 "$SCRIPT_DIR/skill-self-check.py" --skill-root "$SKILL_ROOT" --strict

echo "[7/8] 用户文档审查"
if [[ -n "$PLAN" ]]; then
  python3 "$SCRIPT_DIR/docs-drift-helper.py" --skill-root "$SKILL_ROOT" --plan "$PLAN"
else
  python3 "$SCRIPT_DIR/docs-drift-helper.py" --skill-root "$SKILL_ROOT"
fi

if [[ $DO_COMMIT -eq 1 ]]; then
  echo "[8/8] git commit"
  if git -C "$SKILL_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C "$SKILL_ROOT" add -A
    git -C "$SKILL_ROOT" commit -m "chore(skill): upgrade to v${NEW_VERSION} — ${SLUG}" || true
  else
    echo "      skill 目录不是 git 仓库，跳过提交"
  fi
else
  echo "[8/8] 未指定 --commit，跳过 git 提交"
fi
echo "✅ 收尾完成：v${NEW_VERSION} (${SLUG})"

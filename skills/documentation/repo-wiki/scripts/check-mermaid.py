#!/usr/bin/env python3
"""检测 wiki 中 mermaid 代码块的常见错误。

用法：python3 check-mermaid.py --wiki-root <path>

检查项：
  1. 节点标签中出现字面 \\n（反斜杠 + n）——mermaid 会原样显示，应改用 <br/>
  2. ```mermaid 围栏未闭合
  3. 空的 mermaid 块
退出码：默认始终 0；加 --strict 时存在问题返回 1。
"""
import argparse
import re
import sys
from pathlib import Path

LITERAL_NEWLINE = re.compile(r'\\n')


def scan_file(md, wiki_root):
    rel = md.relative_to(wiki_root)
    problems = []
    lines = md.read_text(encoding='utf-8', errors='ignore').split('\n')
    inside, start, body = False, 0, []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not inside and re.match(r'^(```|~~~)\s*mermaid\b', stripped):
            inside, start, body = True, i, []
            continue
        if inside and re.match(r'^(```|~~~)\s*$', stripped):
            inside = False
            if not any(l.strip() for l in body):
                problems.append((rel, start, '空的 mermaid 块'))
            continue
        if inside:
            body.append(line)
            if LITERAL_NEWLINE.search(line):
                problems.append((rel, i, r'节点标签含字面 \n，应改用 <br/>'))
    if inside:
        problems.append((rel, start, 'mermaid 围栏未闭合'))
    return problems


def main():
    parser = argparse.ArgumentParser(description='检测 mermaid 块中的字面 \\n 等问题')
    parser.add_argument('--wiki-root', required=True, help='wiki 根目录')
    parser.add_argument('--strict', action='store_true', help='存在问题时以退出码 1 结束')
    args = parser.parse_args()

    wiki_root = Path(args.wiki_root).resolve()
    if not wiki_root.is_dir():
        print(f'wiki 根目录不存在: {wiki_root}', file=sys.stderr)
        sys.exit(1)

    problems = []
    blocks = 0
    for md in sorted(wiki_root.rglob('*.md')):
        rel = md.relative_to(wiki_root)
        if any(part.startswith('.') for part in rel.parts[:-1]):
            continue
        blocks += md.read_text(encoding='utf-8', errors='ignore').count('```mermaid')
        problems.extend(scan_file(md, wiki_root))

    for rel, line, msg in problems:
        print(f'  ✗ {rel}:{line} {msg}')
    if problems:
        print(f'✗ 共检查 {blocks} 个 mermaid 块，发现 {len(problems)} 处问题')
        if args.strict:
            sys.exit(1)
    else:
        print('✓ 未发现 mermaid \\n 问题')


if __name__ == '__main__':
    main()

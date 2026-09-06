#!/usr/bin/env python3
"""输出 wiki 统计信息（含逐页字数，用于核对最低字数门槛）。

用法：python3 wiki-stats.py --wiki-root <path> [--min-chars 1800] [--per-page]

页数只统计正文页：排除 INDEX.md / HOW-TO-UPDATE.md / GLOSSARY.md、章节 README.md
以及隐藏目录（.wiki-meta/ 等），因此可直接与 schema 的 target_pages 比较。
"""
import argparse, re
from pathlib import Path
from collections import defaultdict

def count_mermaid(content):
    return len(re.findall(r'```mermaid', content))

def count_chars(content):
    # 统计非空白字符数（中文/英文混合）
    return len(re.sub(r'\s+', '', content))

def count_cjk(content):
    # 中日韩统一表意文字数量：最低字数门槛按「汉字」计时用这个
    return len(re.findall(r'[\u4e00-\u9fff]', content))

def strip_noise(content):
    # 计入字数前去掉 mermaid / 代码块与 front-matter，避免图表和代码撑高字数
    content = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.S)
    return re.sub(r'```.*?```', '', content, flags=re.S)

def count_followup_todos(wiki_root):
    followup = wiki_root / '.followup.md'
    if not followup.exists():
        return 0
    content = followup.read_text(encoding='utf-8', errors='ignore')
    return len(re.findall(r'^- \[ \]', content, re.MULTILINE))

def main():
    parser = argparse.ArgumentParser(description='输出 wiki 统计信息')
    parser.add_argument('--wiki-root', required=True, help='wiki 根目录')
    parser.add_argument('--min-chars', type=int, default=1800,
                        help='每页最低汉字数门槛（默认 1800，与 SKILL.md 验证规范一致）')
    parser.add_argument('--per-page', action='store_true', help='逐页列出字数（默认只列不达标的页）')
    args = parser.parse_args()

    wiki_root = Path(args.wiki_root).resolve()

    total_pages = 0
    total_chars = 0
    total_mermaid = 0
    chapter_stats = defaultdict(int)
    page_rows = []
    EXCLUDE = {'INDEX.md', 'HOW-TO-UPDATE.md', 'GLOSSARY.md', 'README.md'}

    for md_file in sorted(wiki_root.rglob('*.md')):
        rel = md_file.relative_to(wiki_root)
        parts = rel.parts
        # 跳过 .wiki-meta/ 和 HOW-TO-UPDATE.md 等元文件
        if any(part.startswith('.') for part in parts) or parts[-1] in EXCLUDE:
            continue
        content = md_file.read_text(encoding='utf-8', errors='ignore')
        prose = strip_noise(content)
        total_pages += 1
        total_chars += count_chars(content)
        total_mermaid += count_mermaid(content)
        chapter = parts[0] if len(parts) > 1 else '（根目录）'
        chapter_stats[chapter] += 1
        page_rows.append((str(rel), count_cjk(prose), count_chars(prose), count_mermaid(content)))

    glossary = (wiki_root / 'GLOSSARY.md').is_file()
    followup_todos = count_followup_todos(wiki_root)
    followup_ratio = (followup_todos / total_pages * 100) if total_pages > 0 else 0

    print(f'=== Wiki 统计报告 ===')
    print(f'总页数：{total_pages}')
    print(f'总字符数（非空白）：{total_chars:,}')
    print(f'Mermaid 图总数：{total_mermaid}')
    print(f'.followup.md 待办：{followup_todos} 条（占总页数 {followup_ratio:.1f}%）')
    print(f'GLOSSARY.md：{"✓ 存在" if glossary else "✗ 缺失（轮 1 应产出；四份模板都要求术语与它一致）"}')
    if followup_ratio > 10:
        print(f'  ⚠️  待办比例超过 10%，说明 anchor 调研不足')
    below = [r for r in page_rows if r[1] < args.min_chars]
    print(f'\n逐页字数（门槛 {args.min_chars} 汉字，已排除代码块与 mermaid）：')
    rows = page_rows if args.per_page else below
    if not rows:
        print(f'  ✓ {total_pages} 页全部达标')
    for rel, cjk, chars, mm in sorted(rows):
        mark = '✗' if cjk < args.min_chars else '✓'
        print(f'  {mark} {cjk:>5} 汉字 / {chars:>6} 非空白 / {mm} 图  {rel}')
    if below:
        print(f'  ⚠️  {len(below)}/{total_pages} 页未达 {args.min_chars} 汉字门槛，需补写后再收尾')

    print(f'\n各章页数分布：')
    for chapter, count in sorted(chapter_stats.items()):
        bar = '█' * min(count, 40)
        print(f'  {chapter:<30} {count:3} {bar}')

if __name__ == '__main__':
    main()

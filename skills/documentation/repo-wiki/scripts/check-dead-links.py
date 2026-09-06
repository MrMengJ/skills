#!/usr/bin/env python3
"""扫描 wiki 内的死链（相对路径 markdown 链接指向不存在的文件）。

用法：python3 check-dead-links.py --wiki-root <path> [--ignore-pattern <glob>]...

输出：每条死链一行「  ✗ <页面相对路径> → <链接目标>」，末尾打印汇总。
退出码：默认始终 0（供调度器串联后续检查）；加 --strict 时存在死链返回 1。
"""
import argparse
import fnmatch
import re
import sys
from pathlib import Path
from urllib.parse import unquote

# [text](target)  /  [text]: target  两种写法；忽略图片以外的差异（图片同样检查文件存在）
INLINE_LINK = re.compile(r'!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)')
REF_DEF = re.compile(r'^\s{0,3}\[[^\]]+\]:\s*<?(\S+)>?', re.MULTILINE)
FENCE = re.compile(r'^(```|~~~)', re.MULTILINE)
EXTERNAL_PREFIX = ('http://', 'https://', 'mailto:', 'tel:', 'ftp://', 'data:')


def strip_code_blocks(text):
    """去掉围栏代码块，避免把代码里的 [x](y) 当链接。"""
    out, inside = [], False
    for line in text.split('\n'):
        if FENCE.match(line):
            inside = not inside
            continue
        if not inside:
            out.append(line)
    return '\n'.join(out)


def iter_links(text):
    text = strip_code_blocks(text)
    for m in INLINE_LINK.finditer(text):
        yield m.group(1)
    for m in REF_DEF.finditer(text):
        yield m.group(1)


def is_checkable(target):
    if not target or target.startswith('#'):
        return False
    return not target.lower().startswith(EXTERNAL_PREFIX)


def main():
    parser = argparse.ArgumentParser(description='扫描 wiki 内死链')
    parser.add_argument('--wiki-root', required=True, help='wiki 根目录')
    parser.add_argument('--ignore-pattern', action='append', default=[],
                        help='忽略的链接目标 glob（可多次），如 "*.png"')
    parser.add_argument('--strict', action='store_true', help='存在死链时以退出码 1 结束')
    args = parser.parse_args()

    wiki_root = Path(args.wiki_root).resolve()
    if not wiki_root.is_dir():
        print(f'wiki 根目录不存在: {wiki_root}', file=sys.stderr)
        sys.exit(1)

    checked = 0
    dead = []
    for md in sorted(wiki_root.rglob('*.md')):
        rel = md.relative_to(wiki_root)
        if any(part.startswith('.') for part in rel.parts[:-1]):
            continue  # 跳过 .wiki-meta/ 等隐藏目录
        text = md.read_text(encoding='utf-8', errors='ignore')
        for raw in iter_links(text):
            if not is_checkable(raw):
                continue
            target = unquote(raw.split('#', 1)[0].split('?', 1)[0])
            if not target:
                continue
            if any(fnmatch.fnmatch(target, pat) for pat in args.ignore_pattern):
                continue
            checked += 1
            resolved = (md.parent / target) if not target.startswith('/') else (wiki_root / target.lstrip('/'))
            if not resolved.exists():
                dead.append((str(rel), raw))
                print(f'  ✗ {rel} → {raw}')

    print(f'扫描完成：共检查 {checked} 个链接，发现 {len(dead)} 个死链')
    if dead:
        print(f'✗ 发现 {len(dead)} 个死链')
        if args.strict:
            sys.exit(1)
    else:
        print('✓ 无死链')


if __name__ == '__main__':
    main()

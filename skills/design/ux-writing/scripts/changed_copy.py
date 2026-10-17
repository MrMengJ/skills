#!/usr/bin/env python3
"""列出 git 改动里新增或修改的界面文字，或列出整个项目的界面文字。

用法：
  changed_copy.py                    工作区相对 HEAD 的改动（含未跟踪的新文件）
  changed_copy.py --range A..B       两个提交之间的改动
  changed_copy.py --all [路径...]    不看改动，列出这些路径下所有界面文字
  加 --json 输出 JSON；加 --ascii 连纯英文的文字也列出来（英文界面或双语文案表用）
  加 -C 目录 在那个目录里运行
  加 --ext .foo,.bar 把这些扩展名也按普通源码扫一遍（默认范围之外的才需要，可重复写）

默认扫描：tsx jsx ts js mjs vue svelte html swift kt java dart json yaml；
集中文案文件 strings.xml（含 arrays、plurals）、.strings、.xcstrings、.arb、.po、.properties
（application、gradle 这类配置文件除外）；安卓 res 下 layout、menu、xml、navigation 里写死的
android:text、android:hint、android:contentDescription、android:title（@string/ 引用不算）。

不加 --ascii 时只取含中日韩文字的内容（文案表里的英文短语也取）。加了以后：标签里的文字、
title/label/placeholder/aria-label 这类文案属性、toast/alert/message/notification/Modal 和
Text/Button/Toast.makeText/Snackbar.make/setText/setTitle 这类显示调用的参数，单个英文词也取；
className、id、href、type 等属性里的英文不取。日志调用（console、print、Log.* 等）里的文字
不论中英都不取。
文案表指 i18n、locales、translations、lang、messages 目录里的 json、yaml，以及 .strings、
.xcstrings、.arb、.po、.properties、strings.xml；ts/js 只在 i18n、locales、translations 目录
或 en、zh 这类文件名下才算文案表。组件目录里的 messages/Foo.tsx 不算。

每条输出有 file、line、kind、key、text、before、hints。
  key 是文案表里的键名，其他文件为 null。嵌套的键写完整路径（settings.save.title，数组 tips[0]）；
  strings.xml 的数组写 tabs[0]、复数写 items.other；.xcstrings 写「键.语言」，复数再接
  variations.plural.xxx；.po 的键是 msgid。改动模式下文案表按改动后的整份文件解析，所以只改
  一行也有完整路径；取不到整份文件时（比如文件已删）退回按单行解析，只给最近一层。
  strings.xml 里跨行写的 <string> 取不到。
  before 是同一处被删掉的旧文字。hints（留意）只是提醒，不是结论。

只做提取，不做判断：列出来的不一定都是用户看得到的，漏掉的也可能有，
读清单的人要自己对照代码确认。
"""
import argparse
import html
import json
import os
import re
import subprocess
import sys

CODE_EXT = {'.tsx', '.jsx', '.ts', '.js', '.mjs', '.vue', '.svelte', '.html', '.swift', '.kt', '.java', '.dart'}
DATA_EXT = {'.json', '.yaml', '.yml', '.xml', '.strings', '.xcstrings', '.arb', '.po', '.properties'}
SRC_EXT = CODE_EXT | DATA_EXT
JSX_EXT = {'.tsx', '.jsx', '.ts', '.js', '.mjs', '.vue', '.svelte', '.html'}  # 可能有标签文字（.ts 里是模板字符串）
MARKUP_EXT = {'.vue', '.svelte', '.html'}
EXTRA_EXT = set()

SKIP_PATH = re.compile(
    r'(^|/)(node_modules|dist|build|\.next|out|coverage|vendor|__tests__|__mocks__|fixtures?)/'
    r'|\.(test|spec|stories)\.[a-z]+$|\.d\.ts$'
    r'|(^|/)(package|tsconfig|pnpm-lock|package-lock)[^/]*\.json$|(^|/)pnpm-lock\.ya?ml$'
    r'|(^|/)(application|bootstrap|gradle|local|log4j2?|logback|jdbc)[^/]*\.properties$')
STRINGS_XML = re.compile(r'(^|/)res/values[^/]*/[^/]*(strings|arrays|plurals)[^/]*\.xml$|(^|/)(strings|arrays|plurals)[\w.-]*\.xml$')
LAYOUT_XML = re.compile(r'(^|/)res/(layout|menu|xml|navigation)[\w-]*/[^/]+\.xml$')

# 文案表按「目录名加文件类型」判断：messages、lang 这类也常是组件目录，所以脚本类文件只认更明确的目录名。
I18N_DIR_STRONG = re.compile(r'(^|/)(i18n|l10n|locales?|translations?)/', re.I)
I18N_DIR_ANY = re.compile(r'(^|/)(i18n|l10n|locales?|translations?|langs?|messages)/', re.I)
I18N_FILE = re.compile(r'(^|/)((i18n|l10n|locales?|translations?|lang|messages)|(zh|en|ja|ko|fr|de|es|pt|ru|it)([-_][A-Za-z]{2,4})?)\.[^/]+$', re.I)
PROMPT_PATH = re.compile(r'prompt', re.I)

CJK = re.compile(r'[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\u1100-\u11ff\u3130-\u318f\uff66-\uff9f]')
WORD1 = re.compile(r'[A-Za-z]{2,}')
WORD2 = re.compile(r'[A-Za-z]{2,}\s+[A-Za-z]{2,}')
# 整串都是小写的样式类名（flex items-center）；纯英文文案很少这么写
CLASS_LIST = re.compile(r'(?=.*[-:\[])[a-z0-9!:\[\]\-/._%#()=,&>*+@]+(?: [a-z0-9!:\[\]\-/._%#()=,&>*+@]+)+$')
# 单个词只在明确是显示位置时才取，这些长得像标识符或路径的不取
CODE_LIKE = re.compile(r'[_/\\]|\w\.\w|[a-z][A-Z]|\w=\w|^[a-z0-9]+(?:-[a-z0-9]+)+$|^[#$@%]')
PLACEHOLDER = re.compile(r'\$\{[^}]*\}|\$[A-Za-z_]\w*|\\\([^)]*\)|\{\{[^}]*\}\}|\{[^{}]*\}|\\[nrt"\']')
BARE_ENGLISH = re.compile(r"[A-Z][a-z]+[.!?…]*|[A-Z][\w'’,.:&-]*(?: [\w'’,.:&()-]+)+[.!?]?")

STRING = re.compile(r'''"((?:[^"\\\n]|\\.)*)"|'((?:[^'\\\n]|\\.)*)'|`((?:[^`\\]|\\.)*)`''')
JSX_TEXT = re.compile(r'>([^<>{}]*[^\s<>{}][^<>{}]*)<')
COMMENT_LINE = re.compile(r'^\s*(//|/\*|\*|#|<!--|\{/\*)')
# // 只在行首或空白、标点之后才算注释：前面是冒号的是网址，前面是反斜杠的是正则字面量的结尾（/^\/a\//）
COMMENT = re.compile(r'(?<![^\s;,)\]}{(])//|/\*')
COMMENT_MARKUP = re.compile(r'(?<![^\s;,)\]}{(])//|/\*|<!--')
THROW = re.compile(r'\b(throw\s+new\s+\w*(Error|Exception)|new\s+\w*(Error|Exception)|reject)\s*\($')
CALLEE = re.compile(r'([\w$.]+)\s*$')
KEY_BEFORE = re.compile(r'''(?:^|[\s,({;\[])["']?([A-Za-z_$@:][\w$:@.-]*)["']?\s*([=:])\s*\{?\s*$''')
IDENT = re.compile(r'[A-Za-z_$][\w$]*')

LOG_NAMES = {'console', 'log', 'logger', 'Log', 'Logger', 'LOG', 'LOGGER', 'logging', 'Timber', 'Debug', 'debug',
             'print', 'println', 'printf', 'debugPrint', 'NSLog', 'os_log', 'dump', 'slog', 'Napier'}
UI_CALL = re.compile(
    r'(?:^|\.)\$?(?:'
    r'toast|Toast|alert|confirm|prompt|message|Message|ElMessage|ElNotification|ElMessageBox|notification|Notification|notify|'
    r'snackbar|Snackbar|SnackBar|Modal|Dialog|Popup|showToast|showMessage|showModal|showAlert|showDialog|showSnackBar|showSnackbar|'
    r'Text|BasicText|Button|TextButton|ElevatedButton|OutlinedButton|FilledButton|Label|TextField|SecureField|Toggle|Tab|Section|'
    r'Picker|Menu|Link|Tooltip|Chip|NavigationLink|navigationTitle|navigationBarTitle|'
    r'set(?:Text|Title|Subtitle|Message|Hint|Label|Error|ContentDescription|PositiveButton|NegativeButton|NeutralButton)'
    r')(?:\.\w+)?$')
CLASS_CALL = re.compile(r'(?:^|\.)(?:cn|clsx|classNames?|classnames|twMerge|twJoin|cva|tv)$')

# 属性名决定一个字符串是不是显示文字：不是显示文字的直接排除，是的单个词也取。
NON_COPY = {'classname', 'class', 'classnames', 'style', 'key', 'id', 'href', 'src', 'type', 'htmlfor', 'for', 'to',
            'ref', 'as', 'variant', 'size', 'color', 'rel', 'role', 'target', 'method', 'action', 'lang', 'dir',
            'xmlns', 'viewbox', 'd', 'fill', 'stroke', 'width', 'height', 'slot', 'tabindex', 'autocomplete',
            'inputmode', 'icon', 'systemimage', 'csstext'}
COPY_KEYS = {'alt', 'content', 'header', 'footer', 'summary', 'verbatim', 'headline'}
COPY_SUFFIX = re.compile(r'(text|label|title|message|hint|placeholder|caption|description|tooltip|heading)$', re.I)
ARIA_COPY = {'aria-label', 'aria-description', 'aria-placeholder', 'aria-valuetext', 'aria-roledescription'}

# 只是提醒读清单的人多看一眼，不是结论：命中的可能没问题，没命中的也可能有问题。
BRANDS = re.compile(
    r'\b(?:iPhone|iPad|iPod|iOS|iPadOS|macOS|watchOS|tvOS|visionOS|iCloud|iMessage|iTunes|AirPods|AirDrop|AirPlay|'
    r'FaceTime|MacBook|WeChat|GitHub|GitLab|YouTube|LinkedIn|PayPal|WhatsApp|TikTok|DingTalk|OneDrive|PowerPoint|'
    r'JavaScript|TypeScript|WordPress|OpenAI|ChatGPT|PlayStation|HarmonyOS|DeepSeek|eBay)\b')
HINTS = [
    ('代码里的名字或路径', re.compile(
        r'[a-z]+[A-Z][a-zA-Z]+|[a-z]+_[a-z_]+|\.(ya?ml|json|ts|js|env)\b'
        r'|(?:HTTP|http|状态码?|错误码?|错误|返回|响应|code|status|error|Error)\W{0,3}[45]\d\d(?!\d)'
        r'|(?<!\d)[45]\d\d\W{0,2}(?:错误|Error|Not Found|Forbidden|Unauthorized|Bad Request)'
        r'|/[A-Za-z][\w.-]*/[A-Za-z][\w./-]*')),
    ('指代词，读的人知道指什么吗', re.compile(r'(这|那)(一)?(张|轮|段|家|天)|(这|那)(一)?(条|次|项|个)(?![\u3400-\u9fff])|^它|对方')),
    ('像是在猜原因', re.compile(r'可能是|也许是|大概是|或许')),
    ('生造的口语', re.compile(r'没(?!有)\S{1,2}(成|上|掉)(?![功为])|跑一[次下]|挂[到上]')),
    ('对照现有口气', re.compile(r'暂无|您|该\S{1,3}(已|未|暂)|为您|敬请|智能')),
]


def git(args, cwd):
    return subprocess.run(['git', '-c', 'core.quotepath=false'] + args, cwd=cwd, capture_output=True,
                          text=True, encoding='utf-8', errors='replace').stdout


def ext_of(path):
    return os.path.splitext(path)[1].lower()


def wanted(path):
    if SKIP_PATH.search(path):
        return False
    ext = ext_of(path)
    if ext in EXTRA_EXT:
        return True
    if ext == '.xml':
        return bool(STRINGS_XML.search(path) or LAYOUT_XML.search(path))
    return ext in SRC_EXT


def is_catalog(path):
    """是不是集中文案文件（每个值都是一条文案，有键名）。"""
    ext = ext_of(path)
    if ext in ('.strings', '.xcstrings', '.arb', '.po', '.properties'):
        return True
    if ext == '.xml':
        return bool(STRINGS_XML.search(path))
    if ext in ('.json', '.yaml', '.yml'):
        return bool(I18N_DIR_ANY.search(path) or I18N_FILE.search(path))
    if ext in ('.ts', '.js', '.mjs'):
        return bool(I18N_DIR_STRONG.search(path) or I18N_FILE.search(path))
    return False


def fmt_of(path):
    ext = ext_of(path)
    if ext in ('.yaml', '.yml'):
        return 'yaml'
    if ext in ('.strings', '.po', '.properties'):
        return ext[1:]
    if ext == '.xml':
        return 'strings-xml' if STRINGS_XML.search(path) else 'layout-xml'
    if ext in ('.json', '.arb', '.xcstrings', '.ts', '.js', '.mjs') and is_catalog(path):
        return 'json'
    return 'code'


def want_text(text, ascii_ok, strong=False, catalog=False):
    """strong：这个位置本身就是显示文字（标签、文案属性、显示调用的参数、文案表的值）。"""
    if CJK.search(text):
        return True
    if not catalog and CLASS_LIST.match(text):
        return False
    if (ascii_ok or catalog) and WORD2.search(text):
        return True
    plain = PLACEHOLDER.sub(' ', text)  # 占位符里的变量名、点号不算
    return ascii_ok and strong and bool(WORD1.search(plain)) and not CODE_LIKE.search(plain)


# ---------- 普通源码：一行一行取 ----------

def split_strings(code, markup):
    """切出引号包着的片段；同时去掉注释（块注释换成空格，位置不变；行尾注释直接截掉）。"""
    found, pos = [], 0
    while True:
        m = STRING.search(code, pos)
        c = (COMMENT_MARKUP if markup else COMMENT).search(code, pos, m.start() if m else len(code))
        if c:
            end = -1
            if c.group() != '//':
                tail = '-->' if c.group() == '<!--' else '*/'
                end = code.find(tail, c.end())
                end = end + len(tail) if end >= 0 else -1
            if end < 0:
                return code[:c.start()], found
            code = code[:c.start()] + ' ' * (end - c.start()) + code[end:]
            pos = c.start()
            continue
        if not m:
            return code, found
        if m.group(2) is not None and m.start() and code[m.start() - 1].isalnum():
            pos = m.start() + 1  # 英文里的撇号（don't），不是引号；当引号会吞掉后面的文字
            continue
        found.append(m)
        pos = m.end()


def track(code, start, end, stack):
    """stack 里每项是 (括号, 圆括号前面的调用名)。"""
    for i in range(start, end):
        c = code[i]
        if c in '([{':
            cm = CALLEE.search(code, 0, i) if c == '(' else None
            stack.append((c, cm.group(1) if cm else None))
        elif c in ')]}' and stack:
            stack.pop()


def is_log(callee):
    return any(p in LOG_NAMES for p in callee.split('.'))


def key_role(raw, sep):
    """字符串前面的属性名：copy 是显示文字，skip 一定不是，other 说不准。"""
    if raw.startswith('@') or re.match(r'(v-(?!bind)|on[A-Z]|data-)', raw):
        return 'skip'
    name = re.split(r'[.:]', raw.lstrip(':'))[-1]
    low = name.lower()
    if low.startswith('aria-'):
        return 'copy' if low in ARIA_COPY else 'skip'
    if low in NON_COPY or (low == 'name' and sep == '='):  # name= 是表单字段名，name: 常是展示名
        return 'skip'
    if low in COPY_KEYS or COPY_SUFFIX.search(name):
        return 'copy'
    return 'other'


def after_tag(rest, gt):
    """rest[gt] 的 > 是不是某个标签的结尾（排除 a > b 这类比较）。"""
    head = rest[:gt].replace('=>', '')
    lt = head.rfind('<')
    if lt < 0:
        return False
    tail = head[lt + 1:]
    return '>' not in tail and (tail == '' or re.match(r'/?[A-Za-z]', tail) is not None)


def xml_attrs(line):
    return [html.unescape(m.group(1) if m.group(1) is not None else m.group(2))
            for m in re.finditer(r'''\bandroid:(?:text|hint|contentDescription|title)\s*=\s*(?:"([^"]*)"|'([^']*)')''', line)]


def extract(line, path, ascii_ok):
    """从一行普通源码里取出像界面文字的片段，返回 [(种类, 文字)]。"""
    if COMMENT_LINE.match(line):
        return []
    ext = ext_of(path)
    code, matches = split_strings(line, ext in MARKUP_EXT)
    found, stack, pos = [], [], 0
    for m in matches:
        track(code, pos, m.start(), stack)
        pos = m.end()
        text = next(g for g in m.groups() if g is not None)
        if not text.strip():
            continue
        callees = [c for o, c in stack if o == '(' and c]
        if any(is_log(c) for c in callees):
            continue
        before = code[:m.start()].rstrip()
        km = KEY_BEFORE.search(before)
        role = key_role(km.group(1), km.group(2)) if km else None
        if not CJK.search(text) and (role == 'skip' or any(CLASS_CALL.search(c) for c in callees)):
            continue
        direct = bool(stack) and stack[-1][0] == '(' and bool(stack[-1][1]) and bool(UI_CALL.search(stack[-1][1]))
        if want_text(text, ascii_ok, strong=role == 'copy' or (role is None and direct)):
            found.append(('报错（可能显示给用户）' if THROW.search(before) else '字符串', text))
    rest = code
    for m in reversed(matches):
        rest = rest[:m.start()] + ' ' * (m.end() - m.start()) + rest[m.end():]
    hit = False
    for m in JSX_TEXT.finditer(rest):
        t = m.group(1).strip()
        if (ext in JSX_EXT or CJK.search(t)) and want_text(t, ascii_ok, strong=after_tag(rest, m.start())):
            found.append(('标签里的文字', t))
            hit = True
    if not hit and CJK.search(rest):
        # 跨行的标签文字：整行没有引号包着的中文
        t = re.sub(r'<[^>]*>|\{[^}]*\}', ' ', rest).strip(' \t\r\n,;()[]{}<>/')
        if CJK.search(t):
            found.append(('标签里的文字', re.sub(r'\s+', ' ', t)))
    elif not hit and ascii_ok and ext in JSX_EXT and ext != '.ts' and not matches and BARE_ENGLISH.fullmatch(rest.strip()):
        found.append(('标签里的文字', rest.strip()))  # 跨行的英文标签文字，只认首字母大写的整行
    return found


# ---------- 集中文案文件：按格式解析，带键名 ----------

def join_path(segs):
    out = ''
    for s in segs:
        out += s if s.startswith('[') else ('.' if out else '') + s
    return out


def read_quoted(line, i):
    """line[i] 是引号；返回 (内容, 结束位置)，没闭合就读到行尾。"""
    q, j = line[i], i + 1
    while j < len(line) and line[j] != q:
        j += 2 if line[j] == '\\' else 1
    return line[i + 1:j], min(j + 1, len(line))


def jsonlike(lines):
    """JSON 和 JS/TS 对象字面量里的字符串值，返回 [(行号, [键...], 文字)]。"""
    out, stack, key, block = [], [], None, False

    def child_seg():
        if stack and stack[-1][0] == '[':
            stack[-1][2] += 1
            return '[%d]' % (stack[-1][2] - 1)
        return key

    for no, line in enumerate(lines, 1):
        i, n = 0, len(line)
        while i < n:
            c = line[i]
            if block:
                j = line.find('*/', i)
                if j < 0:
                    break
                block, i = False, j + 2
            elif c.isspace():
                i += 1
            elif line.startswith('//', i):
                break
            elif line.startswith('/*', i):
                block, i = True, i + 2
            elif c in '"\'`':
                text, i = read_quoted(line, i)
                rest = line[i:].lstrip()
                if rest.startswith(':') and (not stack or stack[-1][0] == '{'):
                    key, i = text, line.index(':', i) + 1
                elif stack and stack[-1][0] == '(':
                    key = None  # 函数调用的参数，不是文案表的值
                else:
                    seg = child_seg()
                    out.append((no, [f[1] for f in stack if f[1]] + ([seg] if seg else []), text))
                    key = None
            elif IDENT.match(line, i):
                m = IDENT.match(line, i)
                i = m.end()
                if line[i:].lstrip().startswith(':') and (not stack or stack[-1][0] == '{'):
                    key, i = m.group(0), line.index(':', i) + 1
            else:
                if c in '{[(':
                    stack.append([c, None if c == '(' else child_seg(), 0])
                    if c != '(':
                        key = None  # 箭头函数 key: (n) => `...` 的键要留到函数体
                elif c in '}])':
                    if stack:
                        stack.pop()
                    if c != ')':
                        key = None
                elif c in ',;' or (c == '=' and line[i + 1:i + 2] != '>'):
                    key = None
                i += 1
    return out


def json_entries(lines, ext):
    out = []
    for no, segs, text in jsonlike(lines):
        if ext == '.arb' and any(s.startswith('@') for s in segs):
            continue  # @键 下面是给译者看的备注
        if ext == '.xcstrings':
            if segs[-1:] != ['value']:
                continue
            segs = [s for i, s in enumerate(segs[:-1]) if not (i == 0 and s == 'strings') and s not in ('localizations', 'stringUnit')]
        out.append((no, join_path(segs) or None, text))
    return out


YAML_KV = re.compile(r'''^("(?:[^"\\]|\\.)*"|'(?:[^']|'')*'|[^\s"'#\[\]{},&*!|>%@`-][^:#]*?)\s*:(?:\s+(.*))?$''')
YAML_NON_TEXT = {'true', 'false', 'null', '~', 'yes', 'no', 'on', 'off'}


def yaml_scalar(v):
    if v[0] == '"':
        m = re.match(r'"((?:[^"\\]|\\.)*)"', v)
        return m.group(1) if m else v
    if v[0] == "'":
        m = re.match(r"'((?:[^']|'')*)'", v)
        return m.group(1).replace("''", "'") if m else v
    v = re.sub(r'\s+#.*$', '', v).strip()
    return '' if not v or v[0] in '[{*&!%@`#' or v.lower() in YAML_NON_TEXT else v


def yaml_entries(lines, ext=None):
    out, stack, counters, block = [], [], {}, None
    for no, line in enumerate(lines, 1):
        s = line.strip()
        indent = len(line) - len(line.lstrip(' '))
        if block:
            if not s:
                continue
            if indent > block[0]:
                out.append((no, block[1], s))
                continue
            block = None
        if not s or s.startswith('#') or s in ('---', '...'):
            continue
        dash = s == '-' or s.startswith('- ')
        while stack and (stack[-1][0] > indent or (stack[-1][0] == indent and not (dash and not stack[-1][1].startswith('[')))):
            stack.pop()
        col = indent
        while s == '-' or s.startswith('- '):  # 列表项；「- 键: 值」里的键按列表项的下一层算
            base = tuple(x[1] for x in stack)
            idx = counters.get((base, col), 0)
            counters[(base, col)] = idx + 1
            stack.append((col, '[%d]' % idx))
            rest = s[1:]
            col += 1 + len(rest) - len(rest.lstrip(' '))
            s = rest.strip()
        if not s:
            continue
        m = YAML_KV.match(s)
        if m:
            k = m.group(1)
            if k[:1] in '"\'' and k[-1:] == k[:1]:
                k = k[1:-1]
            stack.append((col, k))
            v = (m.group(2) or '').strip()
            if not v or v.startswith('#'):
                continue
            path = join_path([x[1] for x in stack])
            if v[0] in '|>':
                block = (col, path)
                continue
        else:
            v, path = s, join_path([x[1] for x in stack])
        text = yaml_scalar(v)
        if text:
            out.append((no, path or None, text))
    return out


def strings_entries(lines, ext=None):
    rx = re.compile(r'^\s*"((?:[^"\\]|\\.)*)"\s*=\s*"((?:[^"\\]|\\.)*)"\s*;')
    return [(no, m.group(1), m.group(2)) for no, line in enumerate(lines, 1) for m in [rx.match(line)] if m]


def properties_entries(lines, ext=None):
    out, pending = [], None
    for no, line in enumerate(lines, 1):
        if pending:
            pending[2] += line.lstrip()
        else:
            s = line.lstrip()
            m = re.match(r'((?:[^\s:=\\]|\\.)+)\s*[:=]?\s*(.*)$', s) if s and s[0] not in '#!' else None
            if not m:
                continue
            pending = [no, m.group(1), m.group(2)]
        if (len(line) - len(line.rstrip('\\'))) % 2:
            pending[2] = pending[2][:-1]  # 行尾奇数个反斜杠表示下一行接着写
            continue
        out.append((pending[0], pending[1], re.sub(r'\\u([0-9a-fA-F]{4})', lambda x: chr(int(x.group(1), 16)), pending[2])))
        pending = None
    if pending:
        out.append((pending[0], pending[1], pending[2]))
    return out


def po_entries(lines, ext=None):
    out, msgid, cur = [], None, None

    def finish():
        nonlocal msgid
        if cur is None:
            return
        field, no, text = cur
        if field == 'msgid':
            msgid = text
        elif field.startswith('msgstr') and text and msgid != '':  # msgid 为空的是文件头
            out.append((no, msgid or None, text))

    for no, line in enumerate(lines, 1):
        s = line.strip()
        m = re.match(r'(msgid|msgid_plural|msgctxt|msgstr(?:\[\d+\])?)\s+"(.*)"$', s)
        if m:
            finish()
            cur = (m.group(1), no, m.group(2))
        elif s.startswith('"') and s.endswith('"') and len(s) > 1:
            if cur:
                cur = (cur[0], cur[1], cur[2] + s[1:-1])
            else:
                out.append((no, None, s[1:-1]))  # 只拿到单独一行时，不知道属于哪个字段
    finish()
    return out


def android_unescape(text):
    text = re.sub(r'^<!\[CDATA\[(.*)\]\]>$', r'\1', text.strip())
    return re.sub(r'\\(["\'@?])', r'\1', html.unescape(text))


def strings_xml_entries(lines, ext=None):
    out, cont, idx = [], None, 0
    for no, line in enumerate(lines, 1):
        c = re.search(r'<(string-array|plurals)\b[^>]*\bname="([^"]*)"', line)
        if c:
            cont, idx = (c.group(1), c.group(2)), 0
        for m in re.finditer(r'<string\b([^>]*)>(.*?)</string>', line):
            if 'translatable="false"' in m.group(1):
                continue
            name = re.search(r'\bname="([^"]*)"', m.group(1))
            out.append((no, name.group(1) if name else None, android_unescape(m.group(2))))
        for m in re.finditer(r'<item\b([^>]*)>(.*?)</item>', line):
            if not cont:
                continue
            if cont[0] == 'plurals':
                q = re.search(r'quantity="([^"]*)"', m.group(1))
                key = cont[1] + ('.' + q.group(1) if q else '')
            else:
                key, idx = '%s[%d]' % (cont[1], idx), idx + 1
            out.append((no, key, android_unescape(m.group(2))))
        if re.search(r'</(string-array|plurals)>', line):
            cont = None
    return out


def layout_xml_entries(lines, ext=None):
    out = []
    for no, line in enumerate(lines, 1):
        if line.lstrip().startswith('<!--'):
            continue
        out += [(no, None, v) for v in xml_attrs(line) if v and v[0] not in '@?']
    return out


PARSERS = {
    'json': json_entries, 'yaml': yaml_entries, 'strings': strings_entries, 'properties': properties_entries,
    'po': po_entries, 'strings-xml': strings_xml_entries, 'layout-xml': layout_xml_entries,
}


# ---------- 整份文件、改动 ----------

def scan(path, lines, ascii_ok):
    """整份文件 -> [(行号, 种类, 文字, 键名)]，行号从 1 起。"""
    fmt = fmt_of(path)
    if fmt != 'code':
        catalog = is_catalog(path)
        # 非文案表（普通 yaml 之类）里的值不一定是文案，单个英文词不取；安卓布局的属性本身就是文案
        return [(no, '字符串', text, key if catalog else None)
                for no, key, text in PARSERS[fmt](lines, ext_of(path))
                if want_text(text, ascii_ok, strong=catalog or fmt == 'layout-xml', catalog=catalog)]
    out, in_block = [], None
    for no, line in enumerate(lines, 1):
        if in_block:
            if in_block in line:
                in_block = None
            continue
        s = line.lstrip()
        if s.startswith('/*') and '*/' not in s:
            in_block = '*/'
        elif s.startswith('<!--') and '-->' not in s:
            in_block = '-->'
        if in_block:
            continue
        out += [(no, kind, text, None) for kind, text in extract(line, path, ascii_ok)]
    return out


def scan_line(path, line, ascii_ok):
    return [(kind, text, key) for _, kind, text, key in scan(path, [line], ascii_ok)]


def read_text(path):
    try:
        with open(path, 'rb') as f:
            raw = f.read()
    except OSError:
        return None
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):  # Xcode 生成的 .strings 常是 UTF-16
        return raw.decode('utf-16', errors='replace')
    return raw.decode('utf-8-sig', errors='replace')


def lines_of(text):
    # 不能用 splitlines()：它会按 \x0b、\u2028 之类再切一遍，行号就和 git 对不上了
    return [l.rstrip('\r') for l in text.split('\n')]


def item(path, no, kind, text, key, before):
    return {'file': path, 'line': no, 'kind': kind, 'key': key, 'text': text, 'before': before}


def parse_diff(diff):
    """-> [(路径, [{'removed': [行], 'added': [(新行号, 行)]}])]"""
    files, path, hunks, cur, new_no, header = [], None, None, None, 0, False
    for line in diff.split('\n'):
        if line.startswith('diff --git '):
            header, path, cur = True, None, None
            continue
        if header:
            if line.startswith('+++ '):
                p = line[4:].strip()
                path = p[2:] if p.startswith('b/') else None
                if path and not wanted(path):
                    path = None
                if path:
                    hunks = []
                    files.append((path, hunks))
            if not line.startswith('@@'):
                continue
            header = False
        if path is None:
            continue
        if line.startswith('@@'):
            m = re.search(r'\+(\d+)', line)
            new_no = int(m.group(1)) if m else 0
            cur = {'removed': [], 'added': []}
            hunks.append(cur)
        elif cur is None or line.startswith('\\'):
            continue
        elif line.startswith('+'):
            cur['added'].append((new_no, line[1:].rstrip('\r')))
            new_no += 1
        elif line.startswith('-'):
            cur['removed'].append(line[1:].rstrip('\r'))
    return files


def from_diff(diff, ascii_ok, read_new):
    items = []
    for path, hunks in parse_diff(diff):
        whole = None
        if fmt_of(path) != 'code':
            # 文案表要看整份改动后的文件才能给出完整键路径
            text = read_new(path)
            if text is not None:
                whole = {}
                for no, kind, t, key in scan(path, lines_of(text), ascii_ok):
                    whole.setdefault(no, []).append((kind, t, key))
        for h in hunks:
            old = [t for line in h['removed'] for _, t, _ in scan_line(path, line, ascii_ok)]
            new = []
            for no, line in h['added']:
                found = whole.get(no, []) if whole is not None else scan_line(path, line, ascii_ok)
                new += [(no, kind, t, key) for kind, t, key in found]
            new_texts = {t for _, _, t, _ in new}
            gone = [t for t in old if t not in new_texts]
            for no, kind, t, key in new:
                if t in old:
                    continue  # 文字没变，只是代码挪动
                items.append(item(path, no, kind, t, key, gone))
    return items


def scan_path(root, path, ascii_ok):
    text = read_text(os.path.join(root, path)) if wanted(path) else None
    if text is None:
        return []
    return [item(path, no, kind, t, key, []) for no, kind, t, key in scan(path, lines_of(text), ascii_ok)]


def from_files(root, paths, ascii_ok):
    listed = git(['ls-files', '-z', '--cached', '--others', '--exclude-standard', '--'] + (paths or ['.']), root).split('\0')
    items = []
    for path in dict.fromkeys(filter(None, listed)):
        items += scan_path(root, path, ascii_ok)
    return items


def hints_for(text):
    plain = BRANDS.sub(' ', re.sub(r'\$?\{[^{}]*\}', '…', text))  # 占位符里的变量名用户看不到
    return [name for name, rx in HINTS if rx.search(plain)]


def new_side(rng):
    """--range 的右端；写成单个提交时是和工作区比。"""
    m = re.match(r'^(.*?)\.\.\.?(.*)$', rng)
    return (m.group(2) or 'HEAD') if m else None


def main():
    ap = argparse.ArgumentParser(description='列出改动里新增或修改的界面文字')
    ap.add_argument('paths', nargs='*')
    ap.add_argument('--range', dest='rng')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--ascii', action='store_true')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--ext', action='append', default=[], metavar='.foo,.bar', help='补充扫描这些扩展名，逗号分隔')
    ap.add_argument('-C', dest='cwd', default='.')
    a = ap.parse_args()
    for chunk in a.ext:
        for e in chunk.split(','):
            e = e.strip().lower()
            if e:
                EXTRA_EXT.add(e if e.startswith('.') else '.' + e)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, OSError):
        pass

    root = git(['rev-parse', '--show-toplevel'], a.cwd).strip()
    if not root:
        sys.exit('这里不是 git 仓库。没有 git 时用 --all 也不行，请直接读代码找文案。')
    root = os.path.realpath(root)

    def diff_args(*rev):
        return ['diff', '--unified=0', '--no-color', '--no-ext-diff', '--src-prefix=a/', '--dst-prefix=b/'] + list(rev) + ['--'] + a.paths

    def reader(ref):
        if ref is None:
            return lambda p: read_text(os.path.join(root, p))
        return lambda p: git(['show', '%s:%s' % (ref, p)], root) or None

    if a.all:
        # 路径参数是相对运行目录写的，换算成相对仓库根目录
        rel = [os.path.relpath(os.path.realpath(os.path.join(a.cwd, p)), root) for p in a.paths]
        items = from_files(root, rel, a.ascii)
    elif a.rng:
        items = from_diff(git(diff_args(a.rng), a.cwd), a.ascii, reader(new_side(a.rng)))
    else:
        items = from_diff(git(diff_args('HEAD'), a.cwd), a.ascii, reader(None))
        untracked = git(['ls-files', '-z', '--others', '--exclude-standard', '--full-name', '--'] + a.paths, a.cwd)
        for path in filter(None, untracked.split('\0')):
            items += scan_path(root, path, a.ascii)

    for i in items:
        i['hints'] = hints_for(i['text'])
        if PROMPT_PATH.search(i['file']):
            i['hints'].append('文件名带 prompt，可能是写给模型看的，不是界面文字')

    if a.json:
        json.dump(items, sys.stdout, ensure_ascii=False, indent=1)
        return
    if not items:
        print('没有找到新增或修改的界面文字。')
        return
    print(f'共 {len(items)} 条，分布在 {len({i["file"] for i in items})} 个文件。「留意」只是提醒，不是结论。\n')
    last = None
    for i in items:
        if i['file'] != last:
            last = i['file']
            print(f'## {last}')
        where = i['kind'] + (f'，键 {i["key"]}' if i['key'] else '')
        print(f'- 第 {i["line"]} 行（{where}）：{i["text"]}')
        if i['before']:
            print('  - 同一处删掉的：' + ' ｜ '.join(i['before']))
        if i['hints']:
            print('  - 留意：' + '；'.join(i['hints']))


if __name__ == '__main__':
    main()

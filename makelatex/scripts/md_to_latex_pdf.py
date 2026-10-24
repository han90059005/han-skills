#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把带 [n] 交叉引用的 Markdown 转成 LaTeX，并用 XeLaTeX 编译为中文 PDF。

相比旧版的改动：
  * 参考文献改用 thebibliography + \\cite，编号自动、正文角标与会文表同步；
  * 列表 / 表格 / 代码块 / 图片不再被压成流水句；
  * 多遍编译（按 aux 是否稳定决定），产物进 build/，源目录只留 .tex 与 .pdf；
  * 编译失败保留 .log 并回报第一条错误与行号；
  * 章节默认编号（自动收录 PDF 书签），标题自带编号时不重复编号；
  * 页码页脚居中；字体自动在 windows / fandol 间回退。

用法示例：
    python md_to_latex_pdf.py 输入.md --output 输出目录
    python md_to_latex_pdf.py 输入.md --toc --no-compile
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import os
import re
import shutil
import subprocess
import sys

REF_HEADINGS = {"参考文献", "参考文献表", "references", "reference list"}

# ---------------------------------------------------------------- 转义与内联

MATH_RE = re.compile(r"(\$\$.*?\$\$|\$[^$\n]*\$)", re.DOTALL)
CODE_RE = re.compile(r"`([^`\n]+)`")
LINK_RE = re.compile(r"\[([^\]\n]*)\]\(([^)\n]+)\)")
CITE_RE = re.compile(r"\[(\d+(?:\s*[-,，]\s*\d+)*)\]")
NUMBERED_HEADING_RE = re.compile(r"^\s*(?:\d+(?:\.\d+)*|[一二三四五六七八九十百]+)\s*[、.．)）]?\s+\S")
IMAGE_ONLY_RE = re.compile(r"^\s*!\[([^\]]*)\]\(([^)\s]+)\)\s*$")
FENCE_RE = re.compile(r"^\s*```")
LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
TABLE_SEP_RE = re.compile(r"^:?-{2,}:?$")

_CITE_WARNINGS: list[str] = []


def escape_tex(s: str) -> str:
    """转义 LaTeX 特殊字符；* [ ] ` 等留给后续处理。"""
    out = []
    for ch in s:
        if ch == "\\":
            out.append(r"\textbackslash{}")
        elif ch == "{":
            out.append(r"\{")
        elif ch == "}":
            out.append(r"\}")
        elif ch == "#":
            out.append(r"\#")
        elif ch == "$":
            out.append(r"\$")
        elif ch == "%":
            out.append(r"\%")
        elif ch == "&":
            out.append(r"\&")
        elif ch == "_":
            out.append(r"\_")
        elif ch == "~":
            out.append(r"\textasciitilde{}")
        elif ch == "^":
            out.append(r"\textasciicircum{}")
        else:
            out.append(ch)
    return "".join(out)


def _protect(pattern: re.Pattern, s: str, store: list[str], pat_fmt: str = "\x00S%d\x00"):
    """把匹配片段抽出存起来，用占位符代替，避免被后续步骤改写。"""

    def _sub(m):
        store.append(m.group(0))
        return pat_fmt % len(store)

    return pattern.sub(_sub, s)


def _restore(s: str, store: list[str], pat_fmt: str = "\x00S%d\x00", wrap=None):
    for i, seg in enumerate(store, 1):
        s = s.replace(pat_fmt % i, wrap(seg) if wrap else seg)
    return s


def inline_to_tex(s: str, cite: bool = True, ref_nums=None, cite_map=None) -> str:
    """把一行 Markdown 转成 LaTeX：保留数学、行内代码、链接，处理粗体斜体与 [n] 角标。"""
    math_segs: list[str] = []
    code_segs: list[str] = []
    link_segs: list[str] = []

    s = _protect(MATH_RE, s, math_segs, "\x00M%d\x00")
    s = _protect(CODE_RE, s, code_segs, "\x00C%d\x00")

    def _link(m):
        link_segs.append(r"\href{%s}{%s}" % (escape_tex(m.group(2)), escape_tex(m.group(1))))
        return "\x00L%d\x00" % len(link_segs)

    s = LINK_RE.sub(_link, s)
    s = escape_tex(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", s)
    s = re.sub(r"\*(.+?)\*", r"\\textit{\1}", s)

    if cite and ref_nums:
        def _cite(m):
            keys: list[str] = []
            for part in re.split(r"\s*[,，]\s*", m.group(1)):
                if "-" in part:
                    a, _, b = part.partition("-")
                    try:
                        nums = range(int(a), int(b) + 1)
                    except ValueError:
                        return m.group(0)
                else:
                    try:
                        nums = [int(part)]
                    except ValueError:
                        return m.group(0)
                for num in nums:
                    if num in ref_nums:
                        keys.append("ref%d" % (cite_map.get(num, num) if cite_map else num))
                    else:
                        _CITE_WARNINGS.append("正文引用 [%s] 在文献表中不存在，按原文保留" % num)
                        return m.group(0)
            return r"\textsuperscript{\cite{%s}}" % ",".join(keys) if keys else m.group(0)

        s = CITE_RE.sub(_cite, s)

    s = _restore(s, code_segs, "\x00C%d\x00", lambda seg: r"\texttt{%s}" % escape_tex(seg.strip("`")))
    s = _restore(s, link_segs, "\x00L%d\x00")
    s = _restore(s, math_segs, "\x00M%d\x00")
    return s


# ---------------------------------------------------------------- Markdown 解析


def parse_md(text: str):
    lines = [ln.rstrip() for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]

    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1

    title = None
    if i < len(lines) and lines[i].lstrip().startswith("# "):
        title = lines[i].lstrip()[2:].strip()
        i += 1

    author = date = None
    while i < len(lines):
        s = lines[i].strip()
        if not s:
            i += 1
            continue
        if re.search(r"(姓名|学号|作者|Author)", s):
            author = s
            i += 1
            continue
        if re.search(r"(日期|Date|date)", s):
            date = s
            i += 1
            continue
        break

    rest = lines[i:]
    ref_idx = None
    for j, ln in enumerate(rest):
        m = re.match(r"^#{1,3}\s*(.+)$", ln.strip())
        if m and m.group(1).strip().lower() in REF_HEADINGS:
            ref_idx = j
            break

    if ref_idx is None:
        return title, author, date, rest, []

    return title, author, date, rest[:ref_idx], rest[ref_idx + 1:]


def parse_refs(ref_lines: list[str]) -> list[tuple[int, str]]:
    """抽出 '[n] 内容' 条目，按编号排序；无编号的行忽略。"""
    items: list[tuple[int, str]] = []
    for ln in ref_lines:
        s = ln.strip()
        if not s:
            continue
        m = re.match(r"^\[(\d+)\]\s*(.+)$", s)
        if m:
            items.append((int(m.group(1)), m.group(2).strip()))
        else:
            items.append((len(items) + 1, s))
    seen: dict[int, int] = {}
    for n, _ in items:
        seen[n] = seen.get(n, 0) + 1
    for n, c in seen.items():
        if c > 1:
            _CITE_WARNINGS.append("文献表编号 [%d] 重复 %d 次，已按首现保留" % (n, c))
    got = [n for n, _ in items]
    missing = [n for n in range(1, (max(got) if got else 0) + 1) if n not in got]
    if missing:
        _CITE_WARNINGS.append("文献表编号缺 %s，角标将按缺号后的实际顺序排" % ", ".join(str(n) for n in missing))
    uniq: dict[int, str] = {}
    for n, txt in items:
        uniq.setdefault(n, txt)
    return sorted(uniq.items())


def scan_citations(lines: list[str]) -> list[int]:
    """按出现顺序收集正文引用编号（忽略数学内容）。"""
    order: list[int] = []
    for ln in lines:
        if ln.strip().startswith("$$"):
            continue
        for m in CITE_RE.finditer(MATH_RE.sub("", ln)):
            for part in re.split(r"\s*[,，]\s*", m.group(1)):
                if "-" in part:
                    a, _, b = part.partition("-")
                    if a.strip().isdigit() and b.strip().isdigit():
                        order.extend(range(int(a), int(b) + 1))
                elif part.strip().isdigit():
                    order.append(int(part))
    return order


# ---------------------------------------------------------------- 正文渲染


def resolve_image(path: str, md_dir: str, outdir: str):
    """图片按 md 所在目录解析；不在输出目录内则复制到 assets/ 并返回相对路径；缺失返回 None。"""
    cand = path if os.path.isabs(path) else os.path.join(md_dir, path)
    if not os.path.isfile(cand):
        _CITE_WARNINGS.append("图片不存在：%s（已用占位框代替）" % path)
        return None
    root = os.path.abspath(outdir)
    if os.path.abspath(cand).lower().startswith(root.lower() + os.sep):
        return os.path.relpath(cand, outdir).replace("\\", "/")
    assets = os.path.join(outdir, "assets")
    os.makedirs(assets, exist_ok=True)
    safe = "%02d_%s" % (len(os.listdir(assets)) + 1, os.path.basename(cand))
    shutil.copyfile(cand, os.path.join(assets, safe))
    return "assets/" + safe


def _split_cells(row: str) -> list[str]:
    s = row.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _render_table(rows: list[str], ref_nums, cite_map=None) -> list[str]:
    body = []
    ncols = 0
    for row in rows:
        cells = _split_cells(row)
        if cells and all(TABLE_SEP_RE.match(c) for c in cells if c):
            body.append("__SEP__")
            continue
        ncols = max(ncols, len(cells))
        body.append(cells)

    out = [r"\begin{center}", r"\begin{tabular}{%s}" % ("|" + "l|" * max(ncols, 1)), r"\hline"]
    for row in body:
        if row == "__SEP__":
            out.append(r"\hline")
            continue
        cells = row + [""] * (ncols - len(row))
        out.append(" & ".join(inline_to_tex(c, cite=True, ref_nums=ref_nums, cite_map=cite_map) for c in cells) + r" \\")
        out.append(r"\hline")
    out += [r"\end{tabular}", r"\end{center}"]
    return out


def _render_list(items: list[tuple[str, str]], ref_nums, cite_map=None) -> list[str]:
    ordered = any(marker[0].isdigit() for marker, _ in items)
    env = "enumerate" if ordered else "itemize"
    out = [r"\begin{%s}" % env]
    for _, txt in items:
        out.append(r"  \item " + inline_to_tex(txt, cite=True, ref_nums=ref_nums, cite_map=cite_map))
    out.append(r"\end{%s}" % env)
    return out


def render_body(main_lines, ref_nums, toc, star_sections, cite_map=None,
                md_dir=".", outdir=".") -> tuple[str, int]:
    parts: list[str] = []
    sections = 0
    i = 0
    n = len(main_lines)

    # 文档里只要有一处标题自带编号，就认为编号由作者自己维护，全部标题不再自动编号，
    # 避免出现 "0.1 子标题" 这类半自动半手动的错号。
    manual_mode = any(
        NUMBERED_HEADING_RE.match(re.match(r"^#{1,4}\s+(.*)$", ln.strip()).group(1).strip())
        for ln in main_lines
        if re.match(r"^#{1,4}\s+(.*)$", ln.strip())
    )
    auto_number = not (star_sections or manual_mode)

    while i < n:
        raw = main_lines[i]
        s = raw.strip()

        if not s:
            parts.append("")
            i += 1
            continue

        # 代码块
        if FENCE_RE.match(raw):
            i += 1
            block = []
            while i < n and not FENCE_RE.match(main_lines[i]):
                block.append(main_lines[i])
                i += 1
            i += 1  # 跳过结束围栏
            parts.append(r"\begin{verbatim}")
            parts.extend(block)
            parts.append(r"\end{verbatim}")
            continue

        # 独立成行的图片
        m = IMAGE_ONLY_RE.match(s)
        if m:
            alt, path = m.group(1).strip(), m.group(2).strip()
            path = resolve_image(path, md_dir, outdir)
            if path is None:
                parts.append(r"\begin{center}")
                parts.append(r"  \fbox{\parbox{0.7\linewidth}{\centering 图片缺失：%s}}"
                             % escape_tex(alt or "未命名"))
                parts.append(r"\end{center}")
                i += 1
                continue
            parts.append(r"\begin{figure}[htbp]")
            parts.append(r"  \centering")
            parts.append(r"  \includegraphics[width=0.8\linewidth]{%s}" % path)
            if alt:
                parts.append(r"  \caption{%s}" % inline_to_tex(alt, cite=False))
            parts.append(r"\end{figure}")
            i += 1
            continue

        # 表格
        if s.startswith("|") and s.endswith("|") and s.count("|") >= 2:
            rows = []
            while i < n and main_lines[i].strip().startswith("|"):
                rows.append(main_lines[i])
                i += 1
            parts.extend(_render_table(rows, ref_nums, cite_map))
            continue

        # 列表
        if LIST_RE.match(raw):
            items = []
            while i < n:
                m = LIST_RE.match(main_lines[i])
                if not m:
                    break
                items.append((m.group(2), m.group(3)))
                i += 1
            parts.extend(_render_list(items, ref_nums, cite_map))
            continue

        # 引用块
        if s.startswith(">"):
            parts.append(r"\begin{quote}")
            parts.append(inline_to_tex(s.lstrip(">").strip(), cite=True,
                                       ref_nums=ref_nums, cite_map=cite_map))
            parts.append(r"\end{quote}")
            i += 1
            continue

        # 分隔线
        if re.match(r"^(?:-{3,}|\*{3,}|_{3,})$", s):
            parts.append(r"\par\noindent\rule{\linewidth}{0.4pt}\par")
            i += 1
            continue

        # 标题
        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            cmd = {1: "section", 2: "section", 3: "subsection", 4: "subsubsection"}[level]
            sections += 1
            if auto_number:
                parts.append(r"\%s{%s}" % (cmd, inline_to_tex(text, cite=False)))
            else:
                parts.append(r"\phantomsection")
                parts.append(r"\%s*{%s}" % (cmd, inline_to_tex(text, cite=False)))
                parts.append(r"\addcontentsline{toc}{%s}{%s}" % (cmd, escape_tex(text)))
            i += 1
            continue

        parts.append(inline_to_tex(s, cite=True, ref_nums=ref_nums, cite_map=cite_map))
        i += 1

    if toc and sections:
        body = "\n".join(parts)
        return r"\tableofcontents" + "\n\n" + body, sections
    return "\n".join(parts), sections


def render_refs(refs: list[tuple[int, str]]) -> str:
    if not refs:
        return ""
    out = [r"\begin{thebibliography}{99}"]
    for n, txt in refs:
        out.append(r"\bibitem{ref%d} %s" % (n, inline_to_tex(txt, cite=False)))
    out.append(r"\end{thebibliography}")
    return "\n".join(out)


# ---------------------------------------------------------------- 模板


BIB_ENV_OVERRIDE = r"""
% 参考文献：中文标题、不进编号、进书签
\makeatletter
\renewenvironment{thebibliography}[1]{%
  \phantomsection
  \section*{\refname}%
  \addcontentsline{toc}{section}{\refname}%
  \list{\@biblabel{\@arabic\c@enumiv}}%
       {\settowidth\labelwidth{\@biblabel{#1}}%
        \leftmargin\labelwidth \advance\leftmargin\labelsep
        \usecounter{enumiv}%
        \let\p@enumiv\@empty
        \renewcommand\theenumiv{\@arabic\c@enumiv}}%
      \sloppy \clubpenalty4000 \widowpenalty4000 \sfcode`\.\@m}
     {\def\@noitemerr{\@latex@warning{Empty `thebibliography' environment}}%
      \endlist}
\makeatother
"""


def build_tex(title, author, date, body, has_refs: bool, fontset: str, toc: bool = False) -> str:
    out = []
    out.append(r"\documentclass[UTF8,11pt,fontset=%s]{ctexart}" % fontset)
    out.append(r"\usepackage[a4paper,margin=2.5cm]{geometry}")
    out.append(r"\usepackage{amsmath,amssymb}")
    out.append(r"\usepackage{graphicx}")
    out.append(r"\usepackage{setspace}")
    out.append(r"\usepackage{fancyhdr}")
    out.append(r"\usepackage[hidelinks,bookmarksnumbered]{hyperref}")
    if toc:
        out.append(r"\usepackage{tocloft}")
        out.append(r"\renewcommand{\cftsecleader}{\cftdotfill{\cftdotsep}}")
        out.append(r"\renewcommand{\cftsubsecleader}{\cftdotfill{\cftdotsep}}")
    out.append("")
    out.append(r"\onehalfspacing")
    out.append(r"\pagestyle{fancy}")
    out.append(r"\fancyhf{}")
    out.append(r"\fancyfoot[C]{\thepage}")
    out.append(r"\renewcommand{\headrulewidth}{0pt}")
    out.append("")
    if has_refs:
        out.append(BIB_ENV_OVERRIDE.strip())
        out.append("")
    if title:
        out.append(r"\hypersetup{pdftitle={%s}}" % escape_tex(title))
    if author:
        out.append(r"\hypersetup{pdfauthor={%s}}" % escape_tex(author))
    out.append("")
    out.append(r"\begin{document}")
    out.append("")
    out.append(r"\begin{center}")
    out.append(r"{\LARGE\bfseries " + inline_to_tex(title or "", cite=False) + r"}\\[0.6em]")
    if author:
        out.append(r"{\large " + inline_to_tex(author, cite=False) + r"}\\[0.4em]")
    if date:
        out.append(r"{\normalsize " + inline_to_tex(date, cite=False) + r"}")
    out.append(r"\end{center}")
    out.append("")
    out.append(body)
    out.append("")
    out.append(r"\end{document}")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- 编译器定位


def find_xelatex(explicit=None):
    if explicit and os.path.isfile(explicit):
        return explicit
    env = os.environ.get("XELATEX")
    if env and os.path.isfile(env):
        return env
    found = shutil.which("xelatex")
    if found:
        return found
    for pattern in (
        r"D:\AI-tools\latex\texlive\*\bin\windows\xelatex.exe",
        r"D:\texlive\*\bin\windows\xelatex.exe",
        r"C:\texlive\*\bin\windows\xelatex.exe",
    ):
        for p in glob.glob(pattern):
            if os.path.isfile(p):
                return p
    return None


def choose_fontset(explicit: str) -> str:
    if explicit and explicit != "auto":
        return explicit
    for font in ("simsun.ttc", "simhei.ttf"):
        if os.path.isfile(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", font)):
            return "windows"
    return "fandol"


# ---------------------------------------------------------------- 编译


def _aux_signature(build_dir: str, base: str) -> str:
    h = hashlib.sha1()
    for ext in (".aux", ".toc", ".out"):
        p = os.path.join(build_dir, base + ext)
        if os.path.exists(p):
            with open(p, "rb") as f:
                h.update(f.read())
    return h.hexdigest()


def _errors_from_log(log_text: str, limit: int = 3) -> list[str]:
    lines = log_text.splitlines()
    found = []
    for idx, ln in enumerate(lines):
        if ln.startswith("!") or re.match(r"^\.?/?[^:]+:\d+: ", ln):
            snippet = [ln.strip()]
            for nxt in lines[idx + 1: idx + 4]:
                if nxt.strip():
                    snippet.append(nxt.strip())
            found.append("\n      ".join(snippet))
        if len(found) >= limit:
            break
    return found


def compile_tex(xelatex: str, outdir: str, base: str, max_passes: int = 3):
    build_dir = os.path.join(outdir, "build")
    os.makedirs(build_dir, exist_ok=True)
    cmd = [xelatex, "-interaction=nonstopmode", "-file-line-error", "-output-directory", "build", base + ".tex"]
    last_sig = None
    output = ""
    for attempt in range(1, max_passes + 1):
        r = subprocess.run(cmd, cwd=outdir, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
                           timeout=600)
        output = (r.stdout or "") + (r.stderr or "")
        if r.returncode != 0:
            return False, output, attempt, build_dir
        sig = _aux_signature(build_dir, base)
        rerun = "Rerun to get" in output or "Rerun LaTeX" in output or "Please (re)run" in output
        if attempt >= 2 and sig == last_sig and not rerun:
            break
        last_sig = sig
    return True, output, attempt, build_dir


# ---------------------------------------------------------------- 主流程


def main():
    ap = argparse.ArgumentParser(description="带交叉引用的 Markdown 转中文 LaTeX PDF")
    ap.add_argument("input", help="输入 Markdown 文件")
    ap.add_argument("-o", "--output", default=None, help="输出目录（默认与输入同目录）")
    ap.add_argument("--name", default=None, help="输出文件名（不含扩展名）")
    ap.add_argument("--title", default=None)
    ap.add_argument("--author", default=None)
    ap.add_argument("--date", default=None)
    ap.add_argument("--xelatex", default=None, help="xelatex.exe 路径（不指定时自动探测）")
    ap.add_argument("--fontset", default="auto", choices=["auto", "windows", "fandol", "mac"],
                    help="中文字体集（默认自动探测）")
    ap.add_argument("--toc", action="store_true", help="生成目录")
    ap.add_argument("--bib-sort", action="store_true",
                    help="按正文首次引用顺序重排文献编号（GB/T 7714 顺序编码制）")
    ap.add_argument("--star-sections", action="store_true", help="章节不编号（默认编号并进书签）")
    ap.add_argument("--no-compile", action="store_true", help="只生成 .tex")
    ap.add_argument("--keep-log", action="store_true", help="成功后也保留 build/ 下的 .log")
    ap.add_argument("--verbose", action="store_true", help="显示完整编译输出")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        print("错误：找不到输入文件 %s" % args.input, file=sys.stderr)
        return 2

    with open(args.input, encoding="utf-8") as f:
        text = f.read()

    outdir = os.path.abspath(args.output or os.path.dirname(os.path.abspath(args.input)))
    os.makedirs(outdir, exist_ok=True)

    title, author, date, main_lines, ref_lines = parse_md(text)
    title = args.title or title or os.path.splitext(os.path.basename(args.input))[0]
    author = args.author or author
    date = args.date or date

    refs = parse_refs(ref_lines)

    cited = scan_citations(main_lines)
    for num in sorted(set(cited) - {n for n, _ in refs}):
        _CITE_WARNINGS.append("正文引用 [%d] 在文献表中不存在，按原文保留" % num)
    uncited = [n for n, _ in refs if n not in set(cited)]
    if uncited and refs:
        _CITE_WARNINGS.append("文献表第 %s 条未被正文引用" % ", ".join("[%d]" % n for n in uncited))
    ref_nums = {n for n, _ in refs}
    first_order = [n for n in dict.fromkeys(cited) if n in ref_nums]

    cite_map: dict[int, int] = {}
    if args.bib_sort:
        ordered = list(first_order) + [n for n, _ in refs if n not in set(first_order)]
        cite_map = {old: new for new, old in enumerate(ordered, 1)}
        by_num = dict(refs)
        refs = [(cite_map[old], by_num[old]) for old in ordered if old in by_num]
    elif first_order and first_order != [n for n, _ in refs if n in set(first_order)]:
        _CITE_WARNINGS.append("文献表未按正文首次引用顺序编号，可加 --bib-sort 自动重排（GB/T 7714 顺序编码制）")

    body, sections = render_body(main_lines, ref_nums, args.toc, args.star_sections,
                                 cite_map=cite_map,
                                 md_dir=os.path.dirname(os.path.abspath(args.input)),
                                 outdir=os.path.abspath(outdir))
    refs_tex = render_refs(refs)
    if refs_tex:
        body = body + "\n\n" + refs_tex if body else refs_tex

    fontset = choose_fontset(args.fontset)
    tex = build_tex(title, author, date, body, bool(refs), fontset, toc=args.toc)

    base = args.name or os.path.splitext(os.path.basename(args.input))[0]
    tex_path = os.path.join(outdir, base + ".tex")
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex)
    print("已生成 %s（字体集 %s，章节 %d，文献 %d 条%s）"
          % (tex_path, fontset, sections, len(refs), "，含目录" if args.toc else ""))

    for w in dict.fromkeys(_CITE_WARNINGS):
        print("  [提示] " + w)

    if args.no_compile:
        return 0

    if args.xelatex and not os.path.isfile(args.xelatex):
        print("  [提示] 指定的 xelatex 不存在，改用自动探测：%s" % args.xelatex)

    xelatex = find_xelatex(args.xelatex)
    if not xelatex:
        print("错误：找不到 xelatex.exe，请安装 TeX Live 或用 --xelatex 指定路径", file=sys.stderr)
        return 2

    ok, output, passes, build_dir = compile_tex(xelatex, outdir, base,
                                                max_passes=3 if (refs or args.toc) else 2)
    log_path = os.path.join(build_dir, base + ".log")

    if args.verbose:
        print(output)

    if not ok:
        print("编译失败（第 %d 遍），源文件 %s" % (passes, tex_path), file=sys.stderr)
        if os.path.exists(log_path):
            with open(log_path, encoding="utf-8", errors="replace") as f:
                log_text = f.read()
            for e in _errors_from_log(log_text):
                print("  " + e, file=sys.stderr)
            print("完整日志：%s" % log_path, file=sys.stderr)
        return 1

    pdf_src = os.path.join(build_dir, base + ".pdf")
    pdf_dst = os.path.join(outdir, base + ".pdf")
    if not os.path.isfile(pdf_src):
        print("错误：编译完成但没有生成 PDF", file=sys.stderr)
        return 1
    shutil.copyfile(pdf_src, pdf_dst)

    if args.keep_log:
        print("已生成 %s（%d 遍编译，日志 %s）" % (pdf_dst, passes, log_path))
    else:
        shutil.rmtree(build_dir, ignore_errors=True)
        print("已生成 %s（%d 遍编译）" % (pdf_dst, passes))

    warn = output.count("LaTeX Warning")
    if warn:
        print("  [提示] 编译告警 %d 条，用 --keep-log 保留日志查看" % warn)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把带 [n] 交叉引用的 Markdown 转成 LaTeX 并用 tectonic 编译为中文 PDF。

用法示例：
    python md_to_latex_pdf.py 输入.md --output 输出目录 \
        --tectonic D:\\tectonic-0.17.0-x86_64-pc-windows-msvc\\tectonic.exe
"""

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile


REF_HEADINGS = {"参考文献", "参考文献表", "references", "reference list"}


def escape_tex(s: str) -> str:
    """转义 LaTeX 特殊字符；不处理 * [ ] ，后续用于粗体/斜体和角标。"""
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


_MATH_RE = re.compile(r"(\$\$.*?\$\$|\$.*?\$)", re.DOTALL)


def inline_to_tex(s: str, citations: bool = True) -> str:
    """把一行 Markdown 文本转成 LaTeX：保留 $...$ / $$...$$ 数学，粗体、斜体，可选地把 [n] 变成角标。"""
    math_segments = []

    def _protect(m):
        math_segments.append(m.group(1))
        return "\x00M%d\x00" % len(math_segments)

    # 先保护数学片段，避免被 escape_tex 转义（这样 $ _ ^ { } 等在数学模式中可原样保留）
    s = _MATH_RE.sub(_protect, s)
    s = escape_tex(s)
    # 先粗体，再斜体，避免 ** 与 * 互相干扰
    s = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", s)
    s = re.sub(r"\*(.+?)\*", r"\\textit{\1}", s)
    if citations:
        s = re.sub(r"\[(\d+(?:[-,]\d+)*)\]", r"\\textsuperscript{[\1]}", s)
    # 还原数学片段
    for i, seg in enumerate(math_segments, 1):
        s = s.replace("\x00M%d\x00" % i, seg)
    return s


def ref_to_tex(line: str) -> str:
    """把 '[n] ...' 形式的参考文献条目转成 LaTeX，保留开头的 [n] 编号。"""
    m = re.match(r"^(\[\d+\])\s*(.*)$", line)
    if m:
        return m.group(1) + r"\;" + inline_to_tex(m.group(2), citations=False)
    return inline_to_tex(line, citations=False)


def parse_md(text: str):
    lines = [ln.rstrip() for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]

    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1

    title = None
    if i < len(lines) and lines[i].lstrip().startswith("# "):
        title = lines[i].lstrip()[2:].strip()
        i += 1

    author = None
    date = None
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
        main_lines, ref_lines = rest, []
    else:
        main_lines, ref_lines = rest[:ref_idx], rest[ref_idx + 1 :]

    return title, author, date, main_lines, ref_lines


def render_body(main_lines, ref_lines) -> str:
    parts = []
    for ln in main_lines:
        s = ln.strip()
        if not s:
            parts.append("")
            continue
        if s.startswith("### "):
            parts.append(r"\subsection*{" + inline_to_tex(s[4:].strip(), citations=False) + "}")
        elif s.startswith("## "):
            parts.append(r"\section*{" + inline_to_tex(s[3:].strip(), citations=False) + "}")
        elif s.startswith("# "):
            parts.append(r"\section*{" + inline_to_tex(s[2:].strip(), citations=False) + "}")
        else:
            parts.append(inline_to_tex(s, citations=True))

    if ref_lines:
        parts.append("")
        parts.append(r"\section*{参考文献}")
        parts.append(r"\begingroup")
        parts.append(r"\setlength{\parindent}{0pt}")
        parts.append(r"\setlength{\parskip}{4pt}")
        for ln in ref_lines:
            s = ln.strip()
            if not s:
                continue
            parts.append(ref_to_tex(s))
            parts.append("")
        parts.append(r"\endgroup")

    return "\n".join(parts)


def build_tex(title, author, date, body) -> str:
    out = []
    out.append(r"\documentclass[UTF8,11pt,fontset=windows]{ctexart}")
    out.append(r"\usepackage[a4paper,margin=2.5cm]{geometry}")
    out.append(r"\usepackage{setspace}")
    out.append(r"\usepackage[hidelinks]{hyperref}")
    out.append("")
    out.append(r"\onehalfspacing")
    out.append("")
    out.append(r"\begin{document}")
    out.append("")
    out.append(r"\begin{center}")
    out.append(r"{\LARGE\bfseries " + inline_to_tex(title, citations=False) + r"}\\[0.6em]")
    if author:
        out.append(r"{\large " + inline_to_tex(author, citations=False) + r"}\\[0.4em]")
    if date:
        out.append(r"{\normalsize " + inline_to_tex(date, citations=False) + r"}")
    out.append(r"\end{center}")
    out.append("")
    out.append(body)
    out.append("")
    out.append(r"\end{document}")
    return "\n".join(out) + "\n"


def find_tectonic(explicit=None):
    if explicit and os.path.isfile(explicit):
        return explicit
    env = os.environ.get("TECTONIC")
    if env and os.path.isfile(env):
        return env
    found = shutil.which("tectonic")
    if found:
        return found
    for pattern in (r"D:\tectonic*\tectonic.exe", r"D:\tectonic*\*\tectonic.exe"):
        for p in glob.glob(pattern):
            if os.path.isfile(p):
                return p
    return None


def _writable(path: str) -> bool:
    try:
        probe = os.path.join(path, ".codex_write_test")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("x")
        os.remove(probe)
        return True
    except OSError:
        return False


def resolve_cache_dir(explicit: str, tectonic: str) -> str:
    """选择可写的宏包缓存目录。

    默认缓存在 tectonic.exe 同目录的 cache；在受限沙箱下该目录可能只读，
    此时回退到系统临时目录，并尽量从原缓存复制已有宏包，避免重复联网下载。
    """
    candidate = explicit or os.path.join(os.path.dirname(tectonic), "cache")
    os.makedirs(candidate, exist_ok=True)
    if _writable(candidate):
        return candidate
    fallback = os.path.join(tempfile.gettempdir(), "codex-tectonic-cache")
    os.makedirs(fallback, exist_ok=True)
    if os.path.isdir(candidate):
        try:
            for name in os.listdir(candidate):
                src = os.path.join(candidate, name)
                dst = os.path.join(fallback, name)
                if os.path.isdir(src) and not os.path.exists(dst):
                    shutil.copytree(src, dst)
                elif os.path.isfile(src) and not os.path.exists(dst):
                    shutil.copy2(src, dst)
        except OSError:
            pass
    return fallback


def build_env(cache_dir: str) -> dict:
    env = os.environ.copy()
    env["TECTONIC_CACHE_DIR"] = cache_dir
    for key in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        env[key] = ""
    env["NO_PROXY"] = "*"
    env["no_proxy"] = "*"
    return env


def main():
    ap = argparse.ArgumentParser(description="带交叉引用的 Markdown 转中文 LaTeX PDF")
    ap.add_argument("input", help="输入 Markdown 文件")
    ap.add_argument("-o", "--output", default=None, help="输出目录（默认与输入同目录）")
    ap.add_argument("--name", default=None, help="输出文件名（不含扩展名）")
    ap.add_argument("--title", default=None)
    ap.add_argument("--author", default=None)
    ap.add_argument("--date", default=None)
    ap.add_argument("--tectonic", default=None, help="tectonic.exe 路径")
    ap.add_argument("--cache-dir", default=None, help="宏包缓存目录")
    ap.add_argument("--no-compile", action="store_true", help="只生成 .tex")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as f:
        text = f.read()

    title, author, date, main_lines, ref_lines = parse_md(text)
    title = args.title or title or os.path.splitext(os.path.basename(args.input))[0]
    author = args.author or author
    date = args.date or date

    body = render_body(main_lines, ref_lines)
    tex = build_tex(title, author, date, body)

    outdir = args.output or os.path.dirname(os.path.abspath(args.input))
    os.makedirs(outdir, exist_ok=True)
    base = args.name or os.path.splitext(os.path.basename(args.input))[0]
    tex_path = os.path.join(outdir, base + ".tex")
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex)
    print(f"已生成 {tex_path}")

    if args.no_compile:
        return 0

    tectonic = find_tectonic(args.tectonic)
    if not tectonic:
        print("错误：找不到 tectonic.exe，请用 --tectonic 指定路径", file=sys.stderr)
        return 2

    cache_dir = resolve_cache_dir(args.cache_dir, tectonic)
    result = subprocess.run([tectonic, base + ".tex"], cwd=outdir, env=build_env(cache_dir))
    pdf = os.path.join(outdir, base + ".pdf")
    if os.path.exists(pdf):
        print(f"已生成 {pdf}")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())

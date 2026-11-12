#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""tex_to_md.py — 从 LaTeX 源导出与 PDF 一致的 Markdown。

解决三个手工转换容易出错的地方：
  1. 引用编号：解析 paper.bbl 的 \\bibitem 顺序，`[n]` 与 PDF 完全一致（不按 md 首次出现重排）；
  2. 图：figure 环境还原成 `![图注](路径)`，图注里的上标引用转成 `^[n]^`；
  3. 表：longtable 转成管道表，电导率这类上下标转 Unicode。

用法
----
    python tex_to_md.py --tex paper.tex -o 正文.md
    python tex_to_md.py --tex paper.tex --bbl paper.bbl -o 正文.md --number-sections

依赖：pandoc（`pandoc` 在 PATH 中即可）。
"""
from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys

SUP = {"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
       "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "-": "⁻"}
SUB = {"0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅"}

CHAPTERS_HINT = {"引言": 1, "发展脉络与研究现状": 2, "导电高分子的合成与共混改性": 3,
                 "表征方法": 4, "挑战与展望": 5}


def read(path: str) -> str:
    return io.open(path, encoding="utf-8").read()


def parse_bbl(path: str):
    """返回 (key->序号, 序号->条目正文)。"""
    bbl = read(path)
    items = re.split(r"\\bibitem\[[^\]]*\]\{", bbl)[1:]
    key2num, num2text = {}, {}
    for i, chunk in enumerate(items, 1):
        key, rest = chunk.split("}", 1)
        key2num[key.strip()] = i
        num2text[i] = rest
    return key2num, num2text


def clean_ref(s: str) -> str:
    s = s.split("\\end{thebibliography}")[0].replace("\\newblock", " ")
    for pat, rep in ((r"\\doi\{([^}]*)\}", r"DOI:\1"), (r"\\url\{([^}]*)\}", r"\1"),
                     (r"\\href\{[^}]*\}\{([^}]*)\}", r"\1"), (r"\\nolinkurl\{([^}]*)\}", r"\1"),
                     (r"\\Url\{([^}]*)\}", r"\1"), (r"\\textit\{([^}]*)\}", r"*\1*")):
        s = re.sub(pat, rep, s)
    s = s.replace("\\&", "&").replace("~", " ").replace("---", "—").replace("--", "–")
    s = re.sub(r"\s*\\bibitem.*", "", s)
    for mac, rep in (("\\allowbreak", ""), ("\\textasciitilde{}", "~"),
                     ("\\textasciitilde", "~"), ("\\textendash", "–"),
                     ("\\textemdash", "—"), ("\\nobreakspace{}", " "), ("\\ ", " ")):
        s = s.replace(mac, rep)
    return re.sub(r"\s+", " ", s).strip().rstrip(".") + "."


def _strip_macros(s: str) -> str:
    """表格单元格里常见排版宏，pandoc 之前先清掉。"""
    for a, b in (("\\textasciitilde{}", "~"), ("\\textasciitilde", "~"),
                 ("\\allowbreak", ""), ("\\nobreakspace{}", " "),
                 ("\\,", " "), ("\\;", " ")):
        s = s.replace(a, b)
    return s


def math_to_unicode(s: str) -> str:
    for a, b in ((r"\leq", "≤"), (r"\geq", "≥"), (r"\pm", "±"), (r"\approx", "≈"),
                 (r"\times", "×"), (r"\sim", "~"), (r"\pi", "π"), (r"\sigma", "σ"),
                 (r"\varphi", "φ"), (r"\Omega", "Ω"), (r"\infty", "∞")):
        s = s.replace(a, b)
    s = re.sub(r"\^\{([^}]*)\}", lambda m: "".join(SUP.get(c, c) for c in m.group(1)), s)
    s = re.sub(r"_\{([^}]*)\}", lambda m: "".join(SUB.get(c, c) for c in m.group(1)), s)
    s = re.sub(r"\^([0-9\-])", lambda m: SUP.get(m.group(1), m.group(1)), s)
    return s.replace("{", "").replace("}", "").replace("\\", "")


def convert(tex_path: str, bbl_path: str, out_path: str, number_sections: bool = False,
            keep_header: bool = True) -> dict:
    tex = read(tex_path)
    key2num, num2text = parse_bbl(bbl_path)

    m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex, re.S)
    abstract = re.sub(r"\s+", "", m.group(1)).strip() if m else ""
    m2 = re.search(r"\\noindent\\textbf\{关键词：\}([^\n]*)", tex)
    keywords = m2.group(1).strip() if m2 else ""
    mt = re.search(r"\\title\{(.*?)\}\s*\n", tex, re.S)
    title = re.sub(r"\s+", " ", mt.group(1)).strip() if mt else ""
    title = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", "", title).strip()
    title = math_to_unicode(title)

    fig_labels = []
    for blk in re.findall(r"\\begin\{figure\}(?:.*?)\\end\{figure\}", tex, re.S):
        lm = re.search(r"\\label\{(fig:[a-z0-9]+)\}", blk)
        fig_labels.append(lm.group(1) if lm else None)
    fig_num = {lab: i for i, lab in enumerate(fig_labels, 1) if lab}

    body = tex.split("\\begin{document}", 1)[1].split("\\bibliographystyle", 1)[0]
    body = re.sub(r"\\maketitle", "", body)
    body = re.sub(r"\\begin\{abstract\}.*?\\end\{abstract\}", "", body, flags=re.S)
    body = re.sub(r"\\noindent\\textbf\{关键词：\}[^\n]*", "", body)
    body = re.sub(r"\\ref\{(fig:[a-z0-9]+)\}", lambda m: str(fig_num.get(m.group(1), "?")), body)

    body = re.sub(r"\$(.+?)\$", lambda m: math_to_unicode(m.group(1)), body, flags=re.S)
    body = re.sub(r"\\\((.+?)\\\)", lambda m: math_to_unicode(m.group(1)), body, flags=re.S)

    def cite_repl(m):
        nums = sorted({key2num.get(k.strip(), 0) for k in m.group(1).split(",")})
        return "[" + ",".join(str(n) for n in nums if n) + "]"

    body = re.sub(r"\\textsuperscript\{\\cite\{([^}]*)\}\}", lambda m: "^" + cite_repl(m) + "^", body)
    body = re.sub(r"\\citep\{([^}]*)\}", cite_repl, body)
    body = re.sub(r"\\cite\{([^}]*)\}", cite_repl, body)

    def repl_figure(m):
        block = m.group(0)
        p = re.search(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]*)\}", block)
        if not p:
            return ""
        cap_m = re.search(r"\\caption\{(.*)\}\s*\n\s*\\label", block, re.S)
        cap = re.sub(r"\s+", " ", cap_m.group(1)).strip() if cap_m else ""
        return f"\n\nFIGPLACEHOLDER|{p.group(1).strip()}|{cap}\n\n"

    body = re.sub(r"\\begin\{figure\}(?:.*?)\\end\{figure\}", repl_figure, body, flags=re.S)

    tables = []

    def repl_table(m):
        block = m.group(0)
        cap = re.search(r"\\caption\{([^}]*)\}", block)
        cap = cap.group(1).strip() if cap else ""
        rows = []
        for line in block.split("\n"):
            if "&" in line and line.rstrip().endswith("\\\\"):
                cells = [_strip_macros(c.strip()) for c in line.split("&")]
                cells[-1] = cells[-1].rstrip().rstrip("\\").strip()
                rows.append(cells)
        if not rows:
            return ""
        header = rows[0]
        data = [r for r in rows[1:] if r != header]
        md = [f"**表：{cap}**", "", "| " + " | ".join(header) + " |",
              "|" + "|".join(["---"] * len(header)) + "|"]
        md += ["| " + " | ".join(r) + " |" for r in data]
        tables.append("\n".join(md))
        return "\n\nTABLENOPLACEHOLDER\n\n"

    body = re.sub(r"\\begin\{longtable\}(?:.*?)\\end\{longtable\}", repl_table, body, flags=re.S)

    tmp = os.path.join(os.path.dirname(os.path.abspath(out_path)) or ".", "_tmp_tex2md.tex")
    io.open(tmp, "w", encoding="utf-8").write(body)
    try:
        r = subprocess.run(["pandoc", tmp, "-f", "latex", "-t", "markdown", "--wrap=none"],
                           capture_output=True, text=True, encoding="utf-8")
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    if r.returncode != 0:
        sys.exit("pandoc 失败：" + (r.stderr or "")[:400])
    md = r.stdout

    # 图片占位还原（pandoc 会把 | 转义成 \|）
    out = []
    for line in md.split("\n"):
        if "FIGPLACEHOLDER" in line:
            parts = line.replace("\\|", "|").split("|")
            if len(parts) >= 3:
                out.append(f"![{'|'.join(parts[2:]).strip()}]({parts[1].strip()})")
                continue
        out.append(line)
    md = "\n".join(out)

    for a, b in (("\\textasciitilde{}", "~"), ("\\textasciitilde", "~"),
                 ("\\allowbreak", ""), ("\\nobreakspace{}", " "),
                 ("\\[", "["), ("\\]", "]"), ("\\^", "^"), ("\\>", ">"), ("\\~", "~"),
                 ("\\_", "_"), ("\\&", "&"), ("\\#", "#"), ("\\%", "%"), ("\\*", "*")):
        md = md.replace(a, b)
    if tables:
        md = md.replace("TABLENOPLACEHOLDER", tables[0])
    md = re.sub(r"\ \{#[^}]*\}", "", md)
    md = re.sub(r"<!-- -->", "", md)
    md = re.sub(r'"([^"\n]{1,40})"', r"“\1”", md)
    md = re.sub(r"\n{3,}", "\n\n", md)

    # 标题层级：按嵌套深度映射，可选补章号
    lines, sec_i = [], 0
    for line in md.split("\n"):
        m = re.match(r"^(#+)\s+(.*)$", line)
        if not m:
            lines.append(line)
            continue
        depth, name = len(m.group(1)), m.group(2).strip()
        if depth == 1:
            sec_i += 1
            num = CHAPTERS_HINT.get(name, sec_i) if number_sections else None
            lines.append(f"## {num} {name}" if num else f"## {name}")
        else:
            lines.append("#" * min(depth + 1, 6) + " " + name)
    md = "\n".join(lines)

    parts = []
    if keep_header:
        parts.append("<!-- 本文件由 tex_to_md.py 从 LaTeX 源导出，与 PDF 保持同步 -->\n\n")
    if title:
        parts += [f"# {title}\n\n"]
    if abstract:
        parts += ["## 摘要\n\n", abstract, "\n\n"]
    if keywords:
        parts += [f"**关键词：**{keywords}\n\n"]
    parts += [md.strip(), "\n\n## 参考文献\n\n"]
    for i in range(1, len(key2num) + 1):
        parts.append(f"[{i}] {clean_ref(num2text[i])}\n\n")

    io.open(out_path, "w", encoding="utf-8").write("".join(parts))
    stats = {"figures": len(fig_num), "refs": len(key2num), "tables": len(tables),
             "chars": len(re.findall(r"[\u4e00-\u9fa5]", "".join(parts)))}
    return stats


def main():
    ap = argparse.ArgumentParser(prog="tex_to_md.py", description="LaTeX 源导出 Markdown")
    ap.add_argument("--tex", required=True)
    ap.add_argument("--bbl", default=None, help="默认取 --tex 同目录的 paper.bbl")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--number-sections", action="store_true", help="给一级标题补 1..N 编号")
    ap.add_argument("--no-header", action="store_true", help="不写生成说明注释")
    a = ap.parse_args()

    bbl = a.bbl or os.path.join(os.path.dirname(os.path.abspath(a.tex)), "paper.bbl")
    if not os.path.exists(bbl):
        sys.exit(f"找不到 bbl：{bbl}（先编译一次 LaTeX）")
    st = convert(a.tex, bbl, a.out, a.number_sections, not a.no_header)
    print(f"✓ {a.out}：图 {st['figures']} 张、表 {st['tables']} 张、"
          f"参考文献 {st['refs']} 条、汉字 {st['chars']}")


if __name__ == "__main__":
    main()

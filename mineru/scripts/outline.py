#!/usr/bin/env python3
"""生成清洗后 Markdown 的结构摘要：标题树、公式/表格/图片计数、token 估算。

用法: python outline.py <clean.md> [--max-headings N]

只扫结构，不输出正文，用于在"通读全文"之前给用户一份可决策的清单。
"""
import re
import sys


def est_tokens(text):
    cjk = len(re.findall(r"[\u3000-\u9fff\uff00-\uffef]", text))
    other = max(0, len(text) - cjk)
    return int(cjk * 1.0 + other / 3.5)


def main():
    if len(sys.argv) < 2:
        print("usage: outline.py <clean.md> [--max-headings N]", file=sys.stderr)
        sys.exit(2)

    path = sys.argv[1]
    max_headings = 60
    if "--max-headings" in sys.argv:
        i = sys.argv.index("--max-headings")
        if i + 1 < len(sys.argv):
            max_headings = int(sys.argv[i + 1])

    text = open(path, encoding="utf-8", errors="replace").read()
    lines = text.split("\n")

    headings = []
    for lineno, line in enumerate(lines, 1):
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            headings.append((lineno, len(m.group(1)), m.group(2).strip()))

    # 行间公式 $$ ... $$ 与行内 $...$
    display_math = len(re.findall(r"\$\$", text)) // 2
    inline_math = len(re.findall(r"(?<!\$)\$[^$\n]{1,400}\$(?!\$)", text))
    tables = len(re.findall(r"^\|\s*---", text, re.M))
    images = len(re.findall(r"!\[", text))
    placeholders = text.count("<!-- 图")

    print("=== 结构 ===")
    print(f"字符数        : {len(text):,}")
    print(f"估算 token    : ~{est_tokens(text):,}")
    print(f"公式          : 行间 {display_math} 处, 行内 {inline_math} 处")
    print(f"表格          : {tables} 个")
    print(f"图片          : {images} 个（已剥离占位 {placeholders} 个）")

    print()
    print(f"=== 标题（共 {len(headings)} 条，显示前 {min(len(headings), max_headings)}）===")
    for lineno, level, title in headings[:max_headings]:
        indent = "  " * (level - 1)
        print(f"L{lineno:<6} {indent}{'#' * level} {title}")
    if len(headings) > max_headings:
        print(f"... 另有 {len(headings) - max_headings} 条未显示")

    print()
    print("=== 下一步 ===")
    print("把这份摘要交给用户，停下来问他要读哪一部分：")
    print(f"  · 只读某章  -> read 指定行区间（建议 <= 300 行）")
    print(f"  · 只查公式  -> mathreview.py（正文不读）")
    print(f"  · 全文      -> 约 {est_tokens(text):,} token，必须明确确认")


if __name__ == "__main__":
    main()

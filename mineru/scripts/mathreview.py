#!/usr/bin/env python3
"""抽取 Markdown 中的公式及上下文，用于只审公式、不读正文。

用法: python mathreview.py <clean.md> [--start N] [--end N] [--ctx N] [--max M]

输出每处公式的：行号、公式原文、左右上下文（默认各 40 字）。
--start/--end 限定行号范围，便于只审某一章。
"""
import re
import sys


def main():
    argv = sys.argv
    if len(argv) < 2:
        print("usage: mathreview.py <clean.md> [--start N] [--end N] [--ctx N] [--max M]",
              file=sys.stderr)
        sys.exit(2)

    path = argv[1]

    def opt(name, default):
        if name in argv:
            i = argv.index(name)
            if i + 1 < len(argv):
                return int(argv[i + 1])
        return default

    start = opt("--start", 1)
    end = opt("--end", 10 ** 9)
    ctx = opt("--ctx", 40)
    max_items = opt("--max", 200)

    lines = open(path, encoding="utf-8", errors="replace").read().split("\n")

    # 收集公式：行间 $$ 与行内 $...$
    found = []  # (lineno, kind, formula)
    in_block = False
    block_buf = []
    block_start = 0

    for lineno, line in enumerate(lines, 1):
        s = line.strip()
        if s == "$$":
            if not in_block:
                in_block, block_start, block_buf = True, lineno, []
            else:
                found.append((block_start, "block", "\n".join(block_buf).strip()))
                in_block = False
            continue
        if s.startswith("$$") and s.endswith("$$") and len(s) > 4:
            found.append((lineno, "block", s[2:-2].strip()))
            continue
        if in_block:
            block_buf.append(line)
            continue
        for m in re.finditer(r"(?<!\$)\$([^$\n]{1,400})\$(?!\$)", line):
            found.append((lineno, "inline", m.group(1).strip()))

    found = [f for f in found if start <= f[0] <= end]

    print(f"共 {len(found)} 处公式（行 {start}–{end if end < 10**9 else '末'}）")
    print()

    # 可疑特征：常见错误模式
    suspicious = []
    for lineno, kind, formula in found[:max_items]:
        flags = []
        if re.search(r"\\left\s*\||\\right\s*\||\\boxed", formula):
            flags.append("装饰符号(standard 常见幻觉)")
        if re.search(r"[A-Za-z]_\{?[A-Za-z]\}?\s*\(", formula) and "\\frac" in formula:
            flags.append("疑似下标误粘")
        if re.search(r"\\bullet", formula):
            flags.append("多余 \\bullet")
        if re.search(r"\\mathrm\{[a-z]\}", formula):
            flags.append("变量被写正体")

        prefix = f"[L{lineno}]"
        tag = f"  ** {'; '.join(flags)}" if flags else ""
        print(f"{prefix} ({kind}){tag}")
        print(f"    {formula[:300]}")
        # 上下文
        raw = lines[lineno - 1]
        if kind == "inline":
            pos = raw.find("$")
            left = raw[max(0, pos - ctx):pos]
            right_end = raw.find("$", pos + 1) + 1
            right = raw[right_end:right_end + ctx]
            snippet = f"{left}〔公式〕{right}".strip()
            if snippet:
                print(f"    上下文: ...{snippet}...")
        if flags:
            suspicious.append((lineno, flags))
        print()

    if suspicious:
        print("=== 需人工确认 ===")
        for lineno, flags in suspicious:
            print(f"L{lineno}: {'; '.join(flags)}")
        print()
        print("按 SKILL.md 第 7 步：输出「行号 / 原文 / 建议 / 理由」清单，等用户逐条确认后再改。")


if __name__ == "__main__":
    main()

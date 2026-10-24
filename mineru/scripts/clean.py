#!/usr/bin/env python3
"""剥离 MinerU 输出里的 base64 图片，生成可安全阅读的 _clean.md。

用法: python clean.py <in.md> [-o out.md]

MinerU 会把插图内嵌成 ![](data:image/...) ，3 页正文能膨胀到 854 KB。
本脚本把这些行替换成占位注释，并报告剥离前后的体积与 token 估算。
"""
import os
import re
import sys


def est_tokens(text):
    """粗略估算：中日韩字符按 1 token，其余按 3.5 字符/token。"""
    cjk = len(re.findall(r"[\u3000-\u9fff\uff00-\uffef]", text))
    other = max(0, len(text) - cjk)
    return int(cjk * 1.0 + other / 3.5)


def main():
    if len(sys.argv) < 2:
        print("usage: clean.py <in.md> [-o out.md]", file=sys.stderr)
        sys.exit(2)

    src = sys.argv[1]
    dst = None
    if "-o" in sys.argv:
        i = sys.argv.index("-o")
        if i + 1 < len(sys.argv):
            dst = sys.argv[i + 1]
    if dst is None:
        base, ext = os.path.splitext(src)
        dst = f"{base}_clean{ext or '.md'}"

    raw = open(src, encoding="utf-8", errors="replace").read()
    lines = raw.split("\n")

    kept = []
    img_count = 0
    img_bytes = 0
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("![](data:"):
            img_count += 1
            img_bytes += len(line)
            kept.append(f"<!-- 图 {img_count}，已剥离 base64 以节省 token -->")
        else:
            kept.append(line)

    text = "\n".join(kept)
    open(dst, "w", encoding="utf-8").write(text)

    print(f"原文件      : {len(raw.encode('utf-8')) / 1024:.1f} KB  (~{est_tokens(raw)} tokens)")
    print(f"剥离图片    : {img_count} 处, {img_bytes / 1024:.1f} KB")
    print(f"清洗后      : {len(text.encode('utf-8')) / 1024:.1f} KB  (~{est_tokens(text)} tokens)")
    print(f"输出        : {dst}")

    ratio = len(text) / max(1, len(raw))
    if ratio < 0.2:
        print()
        print("提示: 压缩比很高，说明这份文档图片很多。正文文字可能不足以还原内容，")
        print("      涉及图表结论时，建议让用户提供原页截图。")


if __name__ == "__main__":
    main()

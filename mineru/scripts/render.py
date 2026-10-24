#!/usr/bin/env python3
"""把 PDF 页面渲染成 PNG，交给视觉模型直接看。

用法:
  python render.py <pdf> [--pages 1-5] [--dpi 200] [--out <dir>]

用途：
  · 扫描件里带公式的页 —— 渲染出来让模型直接读，比 OCR 准
  · 图表页 —— MinerU 只剥离 base64，想看原图就渲染
  · 校验 —— 核对 MinerU 转出来的公式到底和原页对不对

输出目录默认在源文件旁：<原名>_pages/
"""
import os
import sys


def parse_pages(spec, total):
    if not spec or spec.lower() == "all":
        return list(range(total))
    idx = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            a, b = int(a), int(b)
            idx.extend(range(max(1, a), min(total, b) + 1))
        else:
            v = int(part)
            if 1 <= v <= total:
                idx.append(v)
    return sorted({i - 1 for i in idx})


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)

    path = sys.argv[1]

    def arg(name, default):
        if name in sys.argv:
            i = sys.argv.index(name)
            if i + 1 < len(sys.argv):
                return sys.argv[i + 1]
        return default

    pages_spec = arg("--pages", None)
    dpi = int(arg("--dpi", 200))
    out_dir = arg("--out", os.path.splitext(path)[0] + "_pages")

    if not os.path.exists(path):
        print(f"ERROR: 文件不存在: {path}", file=sys.stderr)
        sys.exit(2)

    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(path)
    total = len(pdf)
    idx = parse_pages(pages_spec, total)

    os.makedirs(out_dir, exist_ok=True)
    scale = dpi / 72.0

    made = []
    for i in idx:
        page = pdf[i]
        bitmap = page.render(scale=scale)
        img = bitmap.to_pil()
        fp = os.path.join(out_dir, f"page_{i + 1:03d}.png")
        img.save(fp)
        made.append(fp)

    print(f"总页数 {total} | 渲染 {len(made)} 页 | {dpi} dpi")
    print(f"输出目录: {out_dir}")
    for fp in made[:10]:
        print(f"  {fp}")
    if len(made) > 10:
        print(f"  ... 另有 {len(made) - 10} 张")
    print()
    print("下一步：用 read_image 直接看这些图（读公式、看图注、核对转换结果）。")


if __name__ == "__main__":
    main()

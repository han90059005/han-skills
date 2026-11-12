#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""compose_figures.py — 把若干张图拼成论文用组图。

三条版式规律已内置：
  1. 同一行内**等高**缩放（不按等宽），宽格自然更宽；
  2. 每行独立高度，宽图可以独占一行；
  3. 白底、统一留白、可选细边框，(a)(b)(c) 标签自动编号。

用法
----
    # 两行：第一行一张，第二行两张，行高分别 880 / 470
    python compose_figures.py -o fig5.png --row a.png --row b.png,c.png --heights 880,470

    # 单行三张，自动标 (a)(b)(c)
    python compose_figures.py -o fig3.png --row a.png,b.png,c.png --height 760

    # 指定某格的标签（不写则自动编号）；不想要标签加 --no-labels
    python compose_figures.py -o f.png --row "a.png=(a),b.png="

    # 只量尺寸：报告像素与 300 dpi 可印宽度
    python compose_figures.py --measure figs/*.png

依赖：Pillow。字体默认找系统中文字体，可用 --font 指定。
"""
from __future__ import annotations

import argparse
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("需要 Pillow：pip install pillow")

DEFAULT_FONTS = [
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
]


def pick_font(explicit: str = "", size: int = 52):
    cands = [explicit] if explicit else []
    cands += DEFAULT_FONTS
    for p in cands:
        if p and os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def load(path: str) -> Image.Image:
    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    return bg.convert("RGB")


def frame(im: Image.Image, pad: int = 16) -> Image.Image:
    out = Image.new("RGB", (im.width + 2 * pad, im.height + 2 * pad), (255, 255, 255))
    out.paste(im, (pad, pad))
    return out


def measure(files):
    rows = []
    for f in files:
        try:
            with Image.open(f) as im:
                w, h = im.size
        except Exception as e:
            rows.append((f, 0, 0, 0, f"打不开：{e}"))
            continue
        rows.append((f, w, h, round(w / 300 * 2.54, 1), ""))
    print(f"{'文件':<40}{'像素':>12}{'可印宽':>9}  备注")
    for f, w, h, cm, note in rows:
        print(f"{os.path.basename(f)[:38]:<40}{f'{w}x{h}':>12}{cm:>8} cm  {note}")
    bad = [r for r in rows if r[3] and r[3] < 8]
    if bad:
        print(f"\n⚠ 有 {len(bad)} 张低于 8 cm 合格线，建议换源或自绘")


def parse_row(spec: str):
    """'a.png=(a),b.png' -> [('a.png','(a)'), ('b.png','')]"""
    items = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            path, label = part.rsplit("=", 1)
            items.append((path.strip(), label.strip()))
        else:
            items.append((part, None))  # None = 自动编号
    return items


def compose(rows, out, heights=None, widths=None, labels=True, pad=40, gutter=34,
            row_gap=26, label_px=52, font_path="", border=0, canvas_width=None):
    for r in rows:
        for path, _ in r:
            if not os.path.exists(path):
                sys.exit(f"找不到图片：{path}")

    # 自动标签
    auto = ord("a")
    prepared = []
    for row in rows:
        items = []
        for path, label in row:
            if label is None:
                label = f"({chr(auto)})" if labels else ""
                auto += 1
            items.append((path, label))
        prepared.append(items)

    if heights and len(heights) != len(prepared):
        sys.exit(f"--heights 需要 {len(prepared)} 个值")
    if widths and len(widths) != len(prepared):
        sys.exit(f"--widths 需要 {len(prepared)} 个值")

    built = []
    for i, items in enumerate(prepared):
        ims = [load(p) for p, _ in items]
        if border:
            ims = [frame(im, border) for im in ims]
        if heights:
            H = heights[i]
            scaled = [(im.resize((max(1, int(im.width * H / im.height)), H), Image.LANCZOS)
                       if im.height != H else im) for im in ims]
        else:
            W = widths[i] if widths else 1600
            per = max(1, len(ims))
            cell = W // per
            scaled = []
            for im in ims:
                r = cell / im.width
                scaled.append((im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))),
                                         Image.LANCZOS))
                               if r != 1 else im)
        built.append([(sim, items[j][1]) for j, sim in enumerate(scaled)])

    row_w = [sum(i.width for i, _ in b) + gutter * (len(b) - 1) for b in built]
    width = max(row_w) + 2 * pad
    if canvas_width:
        width = max(width, canvas_width)
    height = 2 * pad + sum(max(i.height for i, _ in b) + label_px for b in built) \
        + row_gap * (len(built) - 1)

    canvas = Image.new("RGB", (width, height), (255, 255, 255))
    d = ImageDraw.Draw(canvas)
    f = pick_font(font_path, label_px)
    y = pad
    for b in built:
        band_h = max(i.height for i, _ in b)
        x = (width - (sum(i.width for i, _ in b) + gutter * (len(b) - 1))) // 2
        for im, label in b:
            canvas.paste(im, (x, y + label_px + (band_h - im.height) // 2))
            if label:
                d.text((x + 2, y + 2), label, font=f, fill=(25, 25, 25))
            x += im.width + gutter
        y += band_h + label_px + row_gap

    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    canvas.save(out)
    print(f"✓ {out}  {canvas.width}x{canvas.height}  "
          f"（{len(built)} 行，300 dpi 可印宽 {canvas.width / 300 * 2.54:.1f} cm）")
    return canvas


def main():
    ap = argparse.ArgumentParser(prog="compose_figures.py", description="把多张图拼成论文组图")
    ap.add_argument("-o", "--out", help="输出图片路径")
    ap.add_argument("--row", action="append", default=[],
                    help="一行图，逗号分隔；可写 文件=(a) 指定标签。可重复多次")
    ap.add_argument("--height", type=int, default=None, help="所有行统一高度")
    ap.add_argument("--heights", default=None, help="逐行高度，逗号分隔，如 880,470")
    ap.add_argument("--widths", default=None, help="逐行目标宽度（不指定高度时生效）")
    ap.add_argument("--canvas-width", type=int, default=None, help="最小画布宽度")
    ap.add_argument("--no-labels", action="store_true", help="不画 (a)(b)(c)")
    ap.add_argument("--font", default="", help="标签字体路径")
    ap.add_argument("--label-size", type=int, default=52)
    ap.add_argument("--pad", type=int, default=40)
    ap.add_argument("--gutter", type=int, default=34)
    ap.add_argument("--border", type=int, default=0, help="给每格加 N 像素白色细边（0=不加）")
    ap.add_argument("--measure", nargs="+", default=None, help="只量尺寸，不拼图")
    a = ap.parse_args()

    if a.measure:
        measure(a.measure)
        return
    if not a.out or not a.row:
        ap.error("需要 --out 与至少一个 --row")

    heights = [int(x) for x in a.heights.split(",")] if a.heights else \
        ([a.height] * len(a.row) if a.height else None)
    widths = [int(x) for x in a.widths.split(",")] if a.widths else None
    compose([parse_row(r) for r in a.row], a.out, heights=heights, widths=widths,
            labels=not a.no_labels, pad=a.pad, gutter=a.gutter, label_px=a.label_size,
            font_path=a.font, border=a.border, canvas_width=a.canvas_width)


if __name__ == "__main__":
    main()

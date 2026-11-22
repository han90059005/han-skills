# -*- coding: utf-8 -*-
"""Lay panels out on a white grid (2x2 by default) with optional letter labels.

Each input is trimmed of white margins first, then scaled to fit one cell while
keeping its aspect ratio, so panels of very different sizes still line up.

    python compose.py out.png a.png b.png c.png d.png --cols 2 --cell 1080x760
    python compose.py out.png a.png b.png --cols 1 --labels "(a),(b)"
"""
import argparse

from PIL import Image, ImageChops, ImageDraw, ImageFont

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\DejaVuSans-Bold.ttf",
]


def trim(im, thresh=12, pad=10):
    bg = Image.new("RGB", im.size, (255, 255, 255))
    diff = ImageChops.difference(im, bg).convert("L").point(lambda v: 255 if v > thresh else 0)
    bb = diff.getbbox()
    if not bb:
        return im
    l, t, r, b = bb
    return im.crop((max(0, l - pad), max(0, t - pad),
                    min(im.width, r + pad), min(im.height, b + pad)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("images", nargs="+")
    ap.add_argument("--cols", type=int, default=2)
    ap.add_argument("--cell", default="1080x760")
    ap.add_argument("--gap", type=int, default=40)
    ap.add_argument("--margin", type=int, default=30)
    ap.add_argument("--labels", default="", help="comma separated, e.g. (a),(b),(c),(d)")
    a = ap.parse_args()

    cw, ch = (int(v) for v in a.cell.lower().split("x"))
    rows = (len(a.images) + a.cols - 1) // a.cols
    W = a.margin * 2 + cw * a.cols + a.gap * (a.cols - 1)
    H = a.margin * 2 + ch * rows + a.gap * (rows - 1)
    canvas = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(canvas)

    labels = [s.strip() for s in a.labels.split(",")] if a.labels else []
    try:
        font = ImageFont.truetype(FONT_CANDIDATES[0], 34)
    except OSError:
        font = None

    for i, path in enumerate(a.images):
        im = trim(Image.open(path).convert("RGB"))
        s = min((cw - 20) / im.width, (ch - 20) / im.height)
        im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
        r, c = divmod(i, a.cols)
        x = a.margin + c * (cw + a.gap) + (cw - im.width) // 2
        y = a.margin + r * (ch + a.gap) + (ch - im.height) // 2
        canvas.paste(im, (x, y))
        if font and i < len(labels):
            draw.text((a.margin + c * (cw + a.gap) + 8, a.margin + r * (ch + a.gap) + 4),
                      labels[i], font=font, fill=(30, 30, 30))

    canvas.save(a.out)
    print(a.out, canvas.size)


if __name__ == "__main__":
    main()

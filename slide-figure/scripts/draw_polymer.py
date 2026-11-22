# -*- coding: utf-8 -*-
"""Draw a conjugated-polymer repeat unit as a clean schematic (PIL only).

RDKit depicts a 3-hexylthiophene trimer as a staircase, which reads badly in a
textbook-style note. This draws the conventional form instead: one ring, the
alkyl side chain, exocyclic bonds, brackets and a subscript n.

    python draw_polymer.py out.png --label P3HT --side 6

Only the thiophene backbone is implemented -- that covers P3HT / P3OT style
repeat units. Add a branch here for other rings rather than hand-editing the
resulting PNG.
"""
import argparse
import math

from PIL import Image, ImageDraw, ImageFont


def draw_thiophene(d, cx, cy, r, lw, ink, font):
    def pt(deg, rr=r):
        return (cx + rr * math.cos(math.radians(deg)), cy - rr * math.sin(math.radians(deg)))

    S = pt(-90)
    v2, v3, v4, v5 = pt(-18), pt(54), pt(126), pt(198)

    def cut(a, b, gap=26):
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy)
        return (b[0] - dx / n * gap, b[1] - dy / n * gap)

    for a, b in [(v2, v3), (v3, v4), (v4, v5), (v5, S), (S, v2)]:
        if b is S:
            d.line([a, cut(a, S)], fill=ink, width=lw)
        elif a is S:
            d.line([cut(b, S), b], fill=ink, width=lw)
        else:
            d.line([a, b], fill=ink, width=lw)

    for a, b in [(v2, v3), (v4, v5)]:
        ax = a[0] + (cx - a[0]) * 0.16
        ay = a[1] + (cy - a[1]) * 0.16
        bx = b[0] + (cx - b[0]) * 0.16
        by = b[1] + (cy - b[1]) * 0.16
        mx, my = (ax + bx) / 2, (ay + by) / 2
        d.line([(ax + (mx - ax) * 0.18, ay + (my - ay) * 0.18),
                (bx + (mx - bx) * 0.18, by + (my - by) * 0.18)], fill=ink, width=lw)

    tw = d.textlength("S", font=font)
    d.text((S[0] - tw / 2, S[1] - 26), "S", font=font, fill=ink)
    return v2, v3, v5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--label", default="P3HT")
    ap.add_argument("--side", type=int, default=6, help="length of the alkyl side chain")
    ap.add_argument("--size", default="900x830")
    a = ap.parse_args()

    W, H = (int(v) for v in a.size.lower().split("x"))
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    ink = (20, 20, 20)
    lw = max(2, W // 225)
    fc = max(18, W // 21)
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", fc)
        fontb = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", fc + 6)
    except OSError:
        font = fontb = ImageFont.load_default()

    cx, cy, r = W // 2, int(H * 0.53), int(W * 0.122)
    v2, v3, v5 = draw_thiophene(d, cx, cy, r, lw, ink, font)

    # alkyl chain on the beta carbon, vertical zigzag (net drift zero)
    x, y = v3
    step = int(r * 0.53)
    pts = [(x, y)]
    for i in range(a.side):
        ang = 120 if i % 2 == 0 else 60
        x += step * math.cos(math.radians(ang))
        y -= step * math.sin(math.radians(ang))
        pts.append((x, y))
    d.line(pts, fill=ink, width=lw, joint="curve")

    ext = int(r * 0.87)
    d.line([v2, (v2[0] + ext, v2[1])], fill=ink, width=lw)
    d.line([v5, (v5[0] - ext, v5[1])], fill=ink, width=lw)

    BL, BR = v5[0] - ext - int(r * 0.29), v2[0] + ext + int(r * 0.29)
    TL, TB, stub = int(H * 0.05), int(H * 0.80), int(r * 0.24)
    for xb, sgn in ((BL, 1), (BR, -1)):
        d.line([(xb + sgn * stub, TL), (xb, TL)], fill=ink, width=lw)
        d.line([(xb, TL), (xb, TB)], fill=ink, width=lw)
        d.line([(xb, TB), (xb + sgn * stub, TB)], fill=ink, width=lw)
    d.text((BR + 12, TB - fc * 0.7), "n", font=font, fill=ink)

    tw = d.textlength(a.label, font=fontb)
    d.text(((W - tw) / 2, H * 0.88), a.label, font=fontb, fill=(192, 0, 0))

    img.save(a.out)
    print(a.out, img.size)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""Crop a region out of a rendered slide and trim the surrounding white.

Coordinates are pixels in the source image (x1,y1,x2,y2). Get them by rendering
the slide, opening it, and estimating -- or crop generously first, then tighten.

    python crop.py page39.png out.png --box 1030,945,1548,1875 --pad 14
    python crop.py itic.png itic_w.png --box 0,0,1200,700 --whiten 30

--whiten also turns a light-grey slide background into pure white so that a
grid of panels does not show mismatched boxes.
"""
import argparse

from PIL import Image, ImageChops


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--box", required=True, help="x1,y1,x2,y2")
    ap.add_argument("--pad", type=int, default=14)
    ap.add_argument("--thresh", type=int, default=12, help="ink threshold for trim")
    ap.add_argument("--whiten", type=int, default=0,
                    help="pixels brighter than this and near-grey become white")
    a = ap.parse_args()

    im = Image.open(a.src).convert("RGB")
    box = tuple(int(v) for v in a.box.split(","))
    im = im.crop(box)

    if a.whiten:
        px = im.load()
        t = a.whiten
        for y in range(im.height):
            for x in range(im.width):
                r, g, b = px[x, y]
                if min(r, g, b) >= t and max(r, g, b) - min(r, g, b) <= 12:
                    px[x, y] = (255, 255, 255)

    bg = Image.new("RGB", im.size, (255, 255, 255))
    diff = ImageChops.difference(im, bg).convert("L").point(lambda v: 255 if v > a.thresh else 0)
    bb = diff.getbbox()
    if bb:
        l, t, r, b = bb
        im = im.crop((max(0, l - a.pad), max(0, t - a.pad),
                      min(im.width, r + a.pad), min(im.height, b + a.pad)))

    im.save(a.out)
    print(a.out, im.size)


if __name__ == "__main__":
    main()

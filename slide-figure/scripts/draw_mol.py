# -*- coding: utf-8 -*-
"""Draw a 2D chemical structure from SMILES (RDKit), optionally labelled.

    python draw_mol.py "CCCCCCc1ccsc1" out.png --label P3HT
    python draw_mol.py "$SMILES" itic.png --label ITIC --size 1600x900

Needs RDKit.  If it is missing, install into the AI-tools venv (default PyPI is
usually unreachable from here, use a mirror):

    python -m venv D:/AI-tools/rdkit-venv
    D:/AI-tools/rdkit-venv/Scripts/python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple rdkit

Then run this script with D:/AI-tools/rdkit-venv/Scripts/python.exe.

If the result looks like a staircase rather than a chain (polymers!), do not
fight the depiction -- use draw_polymer.py for the repeat-unit form instead.
"""
import argparse
import io
import sys

try:
    from rdkit import Chem
    from rdkit.Chem import rdDepictor
    from rdkit.Chem.Draw import rdMolDraw2D
except ImportError:
    sys.exit("RDKit not available. See the install recipe in this file's docstring.")

from PIL import Image, ImageDraw, ImageFont


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("smiles")
    ap.add_argument("out")
    ap.add_argument("--label", default="")
    ap.add_argument("--size", default="1600x800")
    ap.add_argument("--bracket-n", action="store_true", help="wrap in [ ] with a subscript n")
    a = ap.parse_args()

    w, h = (int(v) for v in a.size.lower().split("x"))
    mol = Chem.MolFromSmiles(a.smiles)
    if mol is None:
        sys.exit("SMILES did not parse: %s" % a.smiles)
    rdDepictor.SetPreferCoordGen(True)
    rdDepictor.Compute2DCoords(mol)

    d = rdMolDraw2D.MolDraw2DCairo(w, h)
    o = d.drawOptions()
    o.bondLineWidth = 3
    o.padding = 0.06
    o.clearBackground = True
    rdMolDraw2D.PrepareAndDrawMolecule(d, mol)
    d.FinishDrawing()

    im = Image.open(io.BytesIO(d.GetDrawingText())).convert("RGB")
    draw = ImageDraw.Draw(im)
    if a.bracket_n:
        draw.line([(10, 10), (10, im.height - 10)], fill=(20, 20, 20), width=4)
        draw.line([(im.width - 10, 10), (im.width - 10, im.height - 10)], fill=(20, 20, 20), width=4)
    if a.label:
        try:
            f = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", max(28, h // 16))
        except OSError:
            f = ImageFont.load_default()
        tw = draw.textlength(a.label, font=f)
        draw.text(((im.width - tw) / 2, im.height - h // 12), a.label, font=f, fill=(192, 0, 0))

    try:
        im.save(a.out)
    except PermissionError:
        sys.exit("Cannot write %s (permission). Write into the working directory instead." % a.out)
    print(a.out, im.size)


if __name__ == "__main__":
    main()

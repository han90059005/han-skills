# -*- coding: utf-8 -*-
"""Render selected slides of a .pptx / .pdf deck to PNG at a chosen DPI.

Why this exists: most lecture decks embed their figures as ~1000 px rasters.
Cropping the embedded image gives a blurry picture; rendering the *slide* at
300 dpi at least keeps text crisp and gives room to crop tightly. It does NOT
recover detail that the embedded raster never had -- if a structure is only
120 px wide on the slide, redraw it (see draw_mol.py / draw_polymer.py).

Usage
-----
    python slides2png.py deck.pptx --outdir ./fig --pages 39,41,44 --dpi 300
    python slides2png.py deck.pdf  --outdir ./fig --pages 1-6    --dpi 200

Output: <outdir>/page39.png ... (1-based slide/page numbers)
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

PS_TEMPLATE = r"""$ErrorActionPreference = "Stop"
$src = '{src}'
$out = '{out}'
$app = New-Object -ComObject PowerPoint.Application
$pres = $app.Presentations.Open($src, $true, $false, $true)
Start-Sleep -Milliseconds 500
$pres.SaveAs($out, 32)
$pres.Close()
$app.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null
Write-Output ("ok " + (Get-Item $out).Length)
"""


def pptx_to_pdf(src, dst):
    """PowerPoint COM export. WithWindow must be $true or PowerPoint refuses."""
    ps1 = os.path.join(tempfile.gettempdir(), "_slides2pdf.ps1")
    body = PS_TEMPLATE.format(src=src.replace("'", "''"), out=dst.replace("'", "''"))
    # Chinese paths need a UTF-8 BOM when the script is read by powershell.exe 5.1
    with open(ps1, "wb") as f:
        f.write(b"\xef\xbb\xbf" + body.encode("utf-8"))
    r = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1],
        capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("PowerPoint COM export failed:\n" + (r.stderr or r.stdout))
    if not os.path.exists(dst):
        sys.exit(
            "PowerPoint reported success but wrote nothing to %s.\n"
            "This happens when the COM step runs inside the bash sandbox -- run the\n"
            "export from the host PowerShell instead (or export the deck to PDF by\n"
            "hand and pass the .pdf to this script)." % dst)


def render(pdf, outdir, pages, dpi):
    made = []
    if shutil.which("pdftoppm"):
        for p in pages:
            base = os.path.join(outdir, "page%d" % p)
            subprocess.run(["pdftoppm", "-f", str(p), "-l", str(p), "-r", str(dpi),
                            "-png", "-singlefile", pdf, base], check=True)
            made.append(base + ".png")
        return made
    try:
        import fitz  # PyMuPDF fallback
    except ImportError:
        sys.exit("Need pdftoppm (poppler) or PyMuPDF (fitz) to rasterise the PDF.")
    doc = fitz.open(pdf)
    for p in pages:
        pix = doc[p - 1].get_pixmap(dpi=dpi)
        out = os.path.join(outdir, "page%d.png" % p)
        pix.save(out)
        made.append(out)
    return made


def parse_pages(spec, total):
    out = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if "-" in chunk:
            a, b = chunk.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        elif chunk:
            out.append(int(chunk))
    return [p for p in out if 1 <= p <= total]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("--outdir", default="fig")
    ap.add_argument("--pages", required=True, help="e.g. 39,41,44 or 1-6")
    ap.add_argument("--dpi", type=int, default=300)
    a = ap.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    deck = os.path.abspath(a.deck)
    pdf = deck
    if deck.lower().endswith((".pptx", ".ppt")):
        pdf = os.path.abspath(os.path.join(
            a.outdir, os.path.splitext(os.path.basename(deck))[0] + ".pdf"))
        if not os.path.exists(pdf):
            pptx_to_pdf(deck, pdf)

    try:
        import fitz as _f
        total = _f.open(pdf).page_count
    except Exception:
        total = 10 ** 6
    pages = parse_pages(a.pages, total)
    for f in render(pdf, a.outdir, pages, a.dpi):
        print(f)


if __name__ == "__main__":
    main()

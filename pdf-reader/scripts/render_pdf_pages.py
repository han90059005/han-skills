"""Render PDF pages to PNG images using PyMuPDF"""
import sys, os, fitz

pdf_path = sys.argv[1]
out_dir = os.path.splitext(pdf_path)[0] + "_pages"
os.makedirs(out_dir, exist_ok=True)

doc = fitz.open(pdf_path)
total = len(doc)
print(f"总页数: {total}")

for i in range(total):
    page = doc[i]
    pix = page.get_pixmap(dpi=200)
    out_path = os.path.join(out_dir, f"page_{i+1:03d}.png")
    pix.save(out_path)

doc.close()
print(f"完成: {total} 页 -> {out_dir}")

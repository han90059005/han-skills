"""快速提取 PDF 文本 - 仅使用 PyMuPDF"""
import sys, os, fitz

pdf_path = sys.argv[1]
out_path = os.path.splitext(pdf_path)[0] + "_extracted.txt"

doc = fitz.open(pdf_path)
print(f"Pages: {len(doc)}")
all_text = []
for i, page in enumerate(doc, 1):
    t = page.get_text()
    if t.strip():
        all_text.append(f"--- 第 {i} 页 ---\n{t}")
doc.close()

text = "\n\n".join(all_text)
with open(out_path, "w", encoding="utf-8") as f:
    f.write(text)
print(f"Done: {len(text)} chars -> {out_path}")

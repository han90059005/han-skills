"""OCR scanned PDF using PyMuPDF + easyocr (Chinese-focused)"""
import sys, os, fitz
import easyocr

pdf_path = sys.argv[1]
out_path = os.path.splitext(pdf_path)[0] + "_ocr.txt"

print(f"正在加载 easyocr (chinese)...")
reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)

doc = fitz.open(pdf_path)
total = len(doc)
print(f"总页数: {total}")

all_text = []
for i in range(total):
    page = doc[i]
    # Render page to image at 200 DPI for better OCR quality
    pix = page.get_pixmap(dpi=200)
    img_bytes = pix.tobytes("png")
    
    # OCR the image
    results = reader.readtext(img_bytes, detail=0)
    page_text = "\n".join(results) if results else ""
    
    if page_text.strip():
        all_text.append(f"--- 第 {i+1} 页 ---\n{page_text}")
    
    if (i+1) % 5 == 0 or i == total - 1:
        print(f"  进度: {i+1}/{total}")

doc.close()

text = "\n\n".join(all_text)
with open(out_path, "w", encoding="utf-8") as f:
    f.write(text)
print(f"完成: {len(text)} 字符 -> {out_path}")

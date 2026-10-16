"""
PDF 阅读器 - 将 PDF 转换为文本
用法: python read_pdf.py <pdf文件路径>

由 pdf-reader skill 调用，自动提取 PDF 文本内容。
"""

import sys
import os


def main():
    if len(sys.argv) < 2:
        print("[错误] 缺少 PDF 文件路径参数")
        print("用法: python read_pdf.py <pdf文件路径>")
        sys.exit(1)

    pdf_path = sys.argv[1]

    if not os.path.exists(pdf_path):
        print(f"[错误] 文件不存在: {pdf_path}")
        sys.exit(1)

    print(f"正在读取: {pdf_path}")
    print("-" * 50)

    text = None
    engine = None

    # 尝试 pdfplumber（排版保留更好）
    try:
        import pdfplumber
        all_text = []
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text()
                if page_text:
                    all_text.append(f"--- 第 {i} 页 ---\n{page_text}")
        text = "\n\n".join(all_text)
        engine = "pdfplumber"
    except ImportError:
        pass
    except Exception as e:
        print(f"[pdfplumber 解析出错] {e}")

    # 回退到 PyMuPDF
    if text is None:
        try:
            import fitz
            all_text = []
            doc = fitz.open(pdf_path)
            for i, page in enumerate(doc, 1):
                page_text = page.get_text()
                if page_text:
                    all_text.append(f"--- 第 {i} 页 ---\n{page_text}")
            doc.close()
            text = "\n\n".join(all_text)
            engine = "PyMuPDF"
        except ImportError:
            pass
        except Exception as e:
            print(f"[PyMuPDF 解析出错] {e}")

    if text is None:
        print("[错误] 没有可用的 PDF 解析库。请运行: uv sync")
        sys.exit(1)

    print(f"[使用 {engine} 解析成功，共 {len(text)} 字符]")
    print("-" * 50)
    print(text)
    print("-" * 50)

    # 保存为文本文件
    base = os.path.splitext(pdf_path)[0]
    output_path = base + "_extracted.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"\n[已保存] {output_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""秒级抽取 PDF 文字层（不跑模型），带页号和 token 闸门。

用法:
  python quickread.py <pdf> [--pages 1-10] [--max-chars 20000] [--save] [--all]

相比走 MinerU：3 页 <1 秒 vs 20+ 秒。适合"只想快速看一眼"。
不适合：扫描件、公式、表格结构。

token 闸门：默认最多输出 20000 字符（约 1 万 token），超出会截断并提示分段。
--all 可强制全文（自担风险）。
"""
import os
import re
import sys


def est_tokens(text):
    cjk = len(re.findall(r"[\u3000-\u9fff\uff00-\uffef]", text))
    other = max(0, len(text) - cjk)
    return int(cjk + other / 3.5)


def parse_pages(spec, total):
    if not spec or spec.lower() == "all":
        return list(range(total))
    idx = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            a, b = int(a), int(b)
            idx.extend(range(max(1, a), min(total, b) + 1))
        else:
            v = int(part)
            if 1 <= v <= total:
                idx.append(v)
    return sorted({i - 1 for i in idx})


def extract(path, idx):
    """返回 [(页号, 文本)]。优先 pypdfium2，回退 pdfplumber / PyMuPDF。"""
    out = []
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(path)
        for i in idx:
            page = pdf[i]
            try:
                tp = page.get_textpage()
                t = tp.get_text_bounded()
            except Exception:
                t = ""
            out.append((i + 1, (t or "").strip()))
        return out, "pypdfium2"
    except ImportError:
        pass

    try:
        import fitz
        doc = fitz.open(path)
        for i in idx:
            out.append((i + 1, doc[i].get_text().strip()))
        doc.close()
        return out, "PyMuPDF"
    except ImportError:
        pass

    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            for i in idx:
                out.append((i + 1, (pdf.pages[i].extract_text() or "").strip()))
        return out, "pdfplumber"
    except ImportError:
        pass

    print("ERROR: 没有可用的 PDF 库。请用 MinerU 环境运行：", file=sys.stderr)
    print(r"  D:\AI-tools\mineru\Scripts\python.exe", file=sys.stderr)
    sys.exit(3)


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)

    path = sys.argv[1]

    def arg(name, default):
        if name in sys.argv:
            i = sys.argv.index(name)
            if i + 1 < len(sys.argv):
                return sys.argv[i + 1]
        return default

    pages_spec = arg("--pages", None)
    max_chars = int(arg("--max-chars", 20000))
    save = "--save" in sys.argv
    show_all = "--all" in sys.argv

    if not os.path.exists(path):
        print(f"ERROR: 文件不存在: {path}", file=sys.stderr)
        sys.exit(2)

    # 先拿总页数
    try:
        import pypdfium2 as pdfium
        total = len(pdfium.PdfDocument(path))
    except Exception:
        import fitz
        doc = fitz.open(path)
        total = len(doc)
        doc.close()

    idx = parse_pages(pages_spec, total)
    pages, engine = extract(path, idx)

    body = "\n\n".join(f"--- 第 {n} 页 ---\n{t}" for n, t in pages if t)
    empty = sum(1 for _, t in pages if not t)

    print(f"[{engine}] {path}")
    print(f"总页数 {total} | 本次读取 {len(idx)} 页 | 空页 {empty} | "
          f"字符 {len(body)} | 约 {est_tokens(body)} token")

    if empty == len(idx):
        print()
        print("全部为空 —— 这是扫描件，没有文字层。")
        print("改用：python probe.py 判定后走 mineru-kit --tier standard")
        sys.exit(4)

    if save:
        out = os.path.splitext(path)[0] + "_extracted.txt"
        open(out, "w", encoding="utf-8").write(body)
        print(f"已保存: {out}")

    print("-" * 60)

    if not show_all and len(body) > max_chars:
        print(body[:max_chars])
        print("-" * 60)
        print(f"[已截断] 全文 {len(body)} 字符，只显示前 {max_chars}。")
        print(f"需要更多 → 用 --pages 指定范围，或 --max-chars 调高。")
        print(f"这是长文档，建议改用 mineru 全流程（有清洗与结构摘要）。")
    else:
        print(body)


if __name__ == "__main__":
    main()

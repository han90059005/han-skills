#!/usr/bin/env python3
"""探测文档：页数、文字层覆盖率、推荐档位。

用法: python probe.py <文件路径>

判定规则:
  structured  覆盖率 >= 0.8  -> basic
  scanned     覆盖率 <= 0.2  -> standard
  mixed       中间           -> standard (basic 在扫描页上会错下标)
  office      pptx/docx 等   -> flash
"""
import json
import os
import sys


def pdf_stats(path):
    try:
        from pypdf import PdfReader
    except ImportError:
        print("ERROR: 缺少 pypdf。请用 MinerU 环境运行：", file=sys.stderr)
        print(r"  D:\AI-tools\mineru\Scripts\python.exe", file=sys.stderr)
        sys.exit(3)

    reader = PdfReader(path)
    n = len(reader.pages)
    if n == 0:
        return 0, 0.0, {}

    # 采样：前 10 页 + 中间 3 页 + 末尾 3 页
    idx = list(range(min(10, n)))
    if n > 12:
        mid = n // 2
        for i in (mid - 1, mid, mid + 1):
            if 0 <= i < n and i not in idx:
                idx.append(i)
        for i in (n - 3, n - 2, n - 1):
            if i not in idx:
                idx.append(i)

    chars = {}
    for i in idx:
        try:
            text = reader.pages[i].extract_text() or ""
        except Exception:
            text = ""
        chars[i + 1] = len(text.strip())  # 1-based 页号

    with_text = sum(1 for c in chars.values() if c >= 20)
    coverage = with_text / len(chars) if chars else 0.0
    return n, coverage, chars


OFFICE_EXT = {
    ".pptx", ".ppt", ".docx", ".doc", ".xlsx", ".xls",
    ".rtf", ".odt", ".ods", ".odp", ".epub", ".ofd",
    ".html", ".htm", ".shtml", ".mhtml", ".mht", ".csv", ".tsv",
}


def main():
    if len(sys.argv) < 2:
        print("usage: probe.py <file>", file=sys.stderr)
        sys.exit(2)

    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"ERROR: 文件不存在: {path}", file=sys.stderr)
        sys.exit(2)

    ext = os.path.splitext(path)[1].lower()
    result = {"file": path, "ext": ext}

    if ext == ".pdf":
        pages, coverage, chars = pdf_stats(path)
        result["pages"] = pages
        result["coverage"] = round(coverage, 3)
        result["sampled_chars"] = chars
        if coverage >= 0.8:
            verdict, tier = "structured", "basic"
        elif coverage <= 0.2:
            verdict, tier = "scanned", "standard"
        else:
            verdict, tier = "mixed", "standard"
        result["verdict"] = verdict
        result["tier"] = tier
    elif ext in OFFICE_EXT:
        result.update(pages=None, coverage=None, verdict="office", tier="flash")
    else:
        result.update(pages=None, coverage=None, verdict="unknown", tier="basic")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print()
    if result["verdict"] == "office":
        print(f"判定: office 文档 -> 档位 flash（原生解析，不跑模型）")
    elif result["verdict"] == "unknown":
        print(f"判定: 未识别格式 {ext}，尝试 basic")
    else:
        pct = result["coverage"] * 100
        print(f"判定: {result['verdict']} | {result['pages']} 页 | "
              f"文字层覆盖率 {pct:.0f}% -> 档位 {result['tier']}")
        print("若判定为 mixed，注意 basic 在扫描页上会错下标，统一用 standard。")


if __name__ == "__main__":
    main()

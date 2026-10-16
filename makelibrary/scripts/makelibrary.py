#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""makelibrary：扫描文献 md 目录，打标签并生成集中索引（JSON + Markdown）。

用法：
    python makelibrary.py --dir 文献目录 --tags tags.json
    python makelibrary.py --dir 文献目录 --tags tags.json --index _index.json

tags.json 示例：
    {"电子皮肤": ["电子皮肤", "e-skin", "electronic skin", "tactile sensor"]}
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time


def read_text(path):
    for enc in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def extract_title(text):
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()
        if s.startswith("#"):
            return s.lstrip("#").strip()
    return ""


def extract_doi(text):
    m = re.search(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", text)
    return m.group(0) if m else ""


def validity_of(text, title):
    n = len(text.strip())
    if n < 80 or not title:
        return "疑似无效"
    low = text.lower()
    if "## 全文" in low:
        return "全文"
    if "## 摘要" in low or n < 3000:
        return "摘要"
    return "全文"


def tag_text(text, tags):
    low = text.lower()
    hits = []
    for tag, kws in tags.items():
        for kw in kws or []:
            if kw and kw.lower() in low:
                hits.append(tag)
                break
    return hits


def signature(path):
    st = os.stat(path)
    return hashlib.md5(
        "{}:{}:{}".format(path, st.st_mtime_ns, st.st_size).encode("utf-8")
    ).hexdigest()


def scan_dir(root):
    out = []
    for dirpath, _dirs, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower().endswith(".md"):
                out.append(os.path.join(dirpath, fn))
    return sorted(out)


def count_by_tag(files):
    counts = {}
    for item in files:
        tags = item.get("tags") or []
        if tags:
            for t in tags:
                counts[t] = counts.get(t, 0) + 1
        else:
            counts["未分类"] = counts.get("未分类", 0) + 1
    return counts


def write_markdown(result, md_path):
    L = ["# 文献索引", "", "> 生成时间：{} ｜ 总文献：{} 篇".format(result["generated_at"], result["total"]), ""]
    L.append("## 标签统计")
    L.append("")
    L.append("| 标签 | 篇数 |")
    L.append("| --- | --- |")
    for tag, cnt in sorted(result["tag_counts"].items(), key=lambda x: -x[1]):
        L.append("| {} | {} |".format(tag, cnt))
    L.append("")
    by_tag = {}
    for item in result["files"]:
        tags = item.get("tags") or ["未分类"]
        for t in tags:
            by_tag.setdefault(t, []).append(item)
    for tag in sorted(by_tag, key=lambda t: -result["tag_counts"].get(t, 0)):
        L.append("## {}（{} 篇）".format(tag, len(by_tag[tag])))
        L.append("")
        for item in by_tag[tag]:
            doi = " ｜ " + item["doi"] if item.get("doi") else ""
            L.append("- **{}** ｜ `{}` ｜ {}{}".format(item["title"], item["path"], item["validity"], doi))
        L.append("")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser(description="扫描文献 md 目录，打标签并生成索引")
    ap.add_argument("--dir", required=True, help="文献 md 目录")
    ap.add_argument("--tags", default=None, help="标签词表 JSON 文件")
    ap.add_argument("--index", default=None, help="索引文件名（默认 _index.json）")
    args = ap.parse_args()

    root = os.path.abspath(args.dir)
    if not os.path.isdir(root):
        print("错误：目录不存在 {}".format(root), file=sys.stderr)
        return 2

    tags = {}
    if args.tags:
        with open(args.tags, "r", encoding="utf-8") as f:
            tags = json.load(f)
    tags_sig = hashlib.md5(
        json.dumps(tags, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()

    index_path = os.path.join(root, args.index or "_index.json")
    old = {}
    old_tags_sig = None
    if os.path.isfile(index_path):
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            old_tags_sig = data.get("tags_sig")
            for item in data.get("files", []):
                old[item.get("path")] = item
        except Exception:
            old = {}

    reuse_ok = old_tags_sig == tags_sig

    files = []
    for full in scan_dir(root):
        rel = os.path.relpath(full, root)
        sig = signature(full)
        prev = old.get(rel)
        if reuse_ok and prev and prev.get("sig") == sig:
            files.append(prev)
            continue
        text = read_text(full)
        title = extract_title(text)
        doi = extract_doi(text)
        validity = validity_of(text, title)
        hits = tag_text(text, tags) if tags else []
        files.append(
            {
                "path": rel,
                "title": title or os.path.splitext(os.path.basename(full))[0],
                "doi": doi,
                "tags": hits,
                "validity": validity,
                "sig": sig,
            }
        )

    result = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(files),
        "tags_sig": tags_sig,
        "tag_counts": count_by_tag(files),
        "files": files,
    }
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    md_path = os.path.splitext(index_path)[0] + ".md"
    write_markdown(result, md_path)

    print("索引已生成：{}".format(index_path))
    print("可读清单：{}".format(md_path))
    print("共 {} 篇文献".format(len(files)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

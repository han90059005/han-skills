#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""paper_finder：关键词检索文献、校验元数据、按分类下载 PDF、生成 Markdown 内容备份。

子命令：
    search KEYWORD  按关键词检索，输出经校验的文献清单（Markdown + JSON）
    get DOI         按 DOI 校验元数据、下载 OA PDF、生成 Markdown 备份

示例：
    python paper_finder.py search "flexible electronic skin" -o 结果目录 --limit 20
    python paper_finder.py get 10.1126/sciadv.1501856 -o 结果目录 --category 柔性电子
"""

import argparse
import json
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request


DEFAULT_MAILTO = "han9005@mail.nwpu.edu.cn"
USER_AGENT = "paper-finder/0.1 (academic use; contact via mailto)"


def _opener():
    """构造直连 opener，绕过本机 HTTP(S) 代理。"""
    proxy = urllib.request.ProxyHandler({})
    ctx = ssl._create_unverified_context()
    return urllib.request.build_opener(proxy, urllib.request.HTTPSHandler(context=ctx))


def http_get(url: str, timeout: int = 40) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with _opener().open(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def http_get_json(url: str, timeout: int = 40):
    return json.loads(http_get(url, timeout=timeout))


def download(url: str, dest: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with _opener().open(req, timeout=90) as resp, open(dest, "wb") as f:
        f.write(resp.read())


def reconstruct_abstract(inverted_index) -> str:
    if not inverted_index:
        return ""
    pos = {}
    for word, idxs in inverted_index.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def slugify(s: str, maxlen: int = 90) -> str:
    s = re.sub(r'[\\/:*?"<>|\r\n]+', " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return (s[:maxlen] or "untitled").strip()


def norm_doi(doi: str) -> str:
    doi = doi.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.lower().startswith(prefix.lower()):
            doi = doi[len(prefix):]
    return doi.strip()


def search_openalex(keyword: str, limit: int, mailto: str):
    q = urllib.parse.quote(keyword)
    url = f"https://api.openalex.org/works?search={q}&per-page={limit}&mailto={urllib.parse.quote(mailto)}"
    data = http_get_json(url)
    results = []
    for w in data.get("results", []):
        doi = norm_doi(w.get("doi") or "")
        authors = [
            (a.get("author") or {}).get("display_name", "")
            for a in w.get("authorships", [])
            if (a.get("author") or {}).get("display_name")
        ]
        source = (w.get("primary_location") or {}).get("source") or {}
        journal = source.get("display_name", "")
        oa = w.get("open_access") or {}
        best = w.get("best_oa_location") or {}
        oa_pdf = best.get("pdf_url") or oa.get("oa_url") or ""
        results.append(
            {
                "title": w.get("display_name", ""),
                "authors": authors,
                "year": w.get("publication_year"),
                "journal": journal,
                "doi": doi,
                "url": f"https://doi.org/{doi}" if doi else (w.get("id") or ""),
                "abstract": reconstruct_abstract(w.get("abstract_inverted_index")),
                "oa_pdf": oa_pdf,
                "cited_by": w.get("cited_by_count"),
                "type": w.get("type") or "",
            }
        )
    return results


def crossref_meta(doi: str) -> dict:
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi)}"
    m = http_get_json(url).get("message", {})
    title = (m.get("title") or [""])[0]
    authors = [
        f"{a.get('given', '')} {a.get('family', '')}".strip()
        for a in m.get("author", [])
    ]
    year = None
    for key in ("published-print", "published-online", "issued"):
        dp = (m.get(key) or {}).get("date-parts") or []
        if dp and dp[0]:
            year = dp[0][0]
            break
    journal = (m.get("container-title") or [""])[0]
    return {"title": title, "authors": authors, "year": year, "journal": journal}


def abstract_by_doi(doi: str) -> str:
    # OpenAlex
    try:
        w = http_get_json(f"https://api.openalex.org/works/https://doi.org/{urllib.parse.quote(doi)}")
        a = reconstruct_abstract(w.get("abstract_inverted_index"))
        if a:
            return a
    except Exception:
        pass
    # Semantic Scholar
    try:
        d = http_get_json(f"https://api.semanticscholar.org/graph/v1/paper/DOI:{urllib.parse.quote(doi)}?fields=abstract")
        if d.get("abstract"):
            return d["abstract"]
    except Exception:
        pass
    return ""


def oa_pdf_url(doi: str, mailto: str) -> str:
    work_url = f"https://api.openalex.org/works/https://doi.org/{urllib.parse.quote(doi)}"
    # 1. OpenAlex 直接给出的 PDF 链接（字段本身就是 PDF）
    try:
        w = http_get_json(work_url)
        pdf = ((w.get("best_oa_location") or {}).get("pdf_url") or "").strip()
        if pdf:
            return pdf
    except Exception:
        pass
    # 2. Unpaywall 的 url_for_pdf（字段本身就是 PDF）
    try:
        u = http_get_json(f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi)}?email={urllib.parse.quote(mailto)}")
        loc = u.get("best_oa_location") or {}
        pdf = (loc.get("url_for_pdf") or "").strip()
        if pdf:
            return pdf
    except Exception:
        pass
    # 3. 仅当 OpenAlex 的 oa_url 看起来是 PDF 才采用
    try:
        oa_url = ((w.get("open_access") or {}).get("oa_url") or "").strip()
        if oa_url.lower().endswith(".pdf"):
            return oa_url
    except Exception:
        pass
    return ""


def extract_pdf_text(pdf_path: str) -> str:
    for mod in ("pypdf", "pdfplumber"):
        try:
            if mod == "pypdf":
                import pypdf
                reader = pypdf.PdfReader(pdf_path)
                return "\n\n".join((p.extract_text() or "") for p in reader.pages)
            else:
                import pdfplumber
                with pdfplumber.open(pdf_path) as pdf:
                    return "\n\n".join((p.extract_text() or "") for p in pdf.pages)
        except Exception:
            continue
    return ""


def cmd_search(args):
    results = search_openalex(args.keyword, args.limit, args.mailto)
    outdir = args.output or "."
    os.makedirs(outdir, exist_ok=True)
    slug = slugify(args.keyword, 50)

    json_path = os.path.join(outdir, f"search_{slug}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    lines = [f"# 检索结果：{args.keyword}", ""]
    for i, r in enumerate(results, 1):
        lines.append(f"## [{i}] {r['title']}")
        if r["authors"]:
            lines.append(f"- 作者：{', '.join(r['authors'])}")
        if r["year"]:
            lines.append(f"- 年份：{r['year']}")
        if r["journal"]:
            lines.append(f"- 期刊：{r['journal']}")
        if r["doi"]:
            lines.append(f"- DOI：{r['url']}")
        if r["oa_pdf"]:
            lines.append(f"- OA PDF：{r['oa_pdf']}")
        if r["abstract"]:
            lines.append(f"- 摘要：{r['abstract']}")
        lines.append("")

    md_path = os.path.join(outdir, f"search_{slug}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(md_path)


def cmd_get(args):
    doi = norm_doi(args.doi)
    try:
        meta = crossref_meta(doi)
    except Exception:
        meta = {"title": args.title or doi, "authors": [], "year": None, "journal": ""}

    title = args.title or meta.get("title") or doi
    abstract = abstract_by_doi(doi)
    oa_pdf = oa_pdf_url(doi, args.mailto)
    category = args.category or "未分类"

    outdir = os.path.join(args.output or ".", category)
    os.makedirs(outdir, exist_ok=True)
    slug = slugify(title, 90)

    lines = [f"# {title}", ""]
    if meta.get("authors"):
        lines.append(f"**作者**：{', '.join(meta['authors'])}")
    if meta.get("year"):
        lines.append(f"**年份**：{meta['year']}")
    if meta.get("journal"):
        lines.append(f"**期刊**：{meta['journal']}")
    lines.append(f"**DOI**：https://doi.org/{doi}")
    if abstract:
        lines += ["", "## 摘要", "", abstract]

    pdf_path = None
    if oa_pdf:
        try:
            pdf_path = os.path.join(outdir, slug + ".pdf")
            download(oa_pdf, pdf_path)
            with open(pdf_path, "rb") as fh:
                head = fh.read(4)
            if head == b"%PDF":
                full = extract_pdf_text(pdf_path)
                if full:
                    lines += ["", "## 全文（自动提取）", "", full]
            else:
                os.remove(pdf_path)
                pdf_path = None
        except Exception:
            if pdf_path and os.path.exists(pdf_path):
                os.remove(pdf_path)
            pdf_path = None

    if pdf_path is None:
        lines += [
            "",
            "## 下载",
            "",
            f"未找到可自动下载的开放获取 PDF，请访问 DOI 链接手动下载：https://doi.org/{doi}",
        ]

    md_path = os.path.join(outdir, slug + ".md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"MD: {md_path}")
    if pdf_path:
        print(f"PDF: {pdf_path}")
    else:
        print(f"未自动下载 PDF：https://doi.org/{doi}")


def main():
    ap = argparse.ArgumentParser(prog="paper_finder.py", description="文献检索、下载与 Markdown 备份")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="按关键词检索文献")
    s.add_argument("keyword")
    s.add_argument("-o", "--output", default=".")
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--mailto", default=DEFAULT_MAILTO)
    s.set_defaults(func=cmd_search)

    g = sub.add_parser("get", help="按 DOI 下载并生成 Markdown 备份")
    g.add_argument("doi")
    g.add_argument("-o", "--output", default=".")
    g.add_argument("--category", default="未分类")
    g.add_argument("--title", default=None)
    g.add_argument("--mailto", default=DEFAULT_MAILTO)
    g.set_defaults(func=cmd_get)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())

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
import html
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


def clean_text(s: str) -> str:
    """去掉 Crossref/OpenAlex 元数据里的 HTML 标签与实体（如 <sub>2</sub>、&amp;）。"""
    s = re.sub(r"<[^>]+>", "", s or "")
    return html.unescape(s).strip()


# 来源类型：OpenAlex / Crossref 的 type 字段归一化，供 makepaper 判断「原始研究 / 综述 / 预印本」。
TYPE_LABELS = {
    "article": "期刊论文",
    "journal-article": "期刊论文",
    "review": "综述",
    "preprint": "预印本",
    "posted-content": "预印本",
    "proceedings-article": "会议论文",
    "book-chapter": "图书章节",
    "book": "图书",
    "dissertation": "学位论文",
    "report": "报告",
    "dataset": "数据集",
    "software": "软件",
    "letter": "通讯/快报",
    "editorial": "社论",
    "erratum": "勘误",
    "paratext": "其他（非研究性）",
    "peer-review": "同行评审记录",
    "component": "其他",
}


def type_label(raw: str) -> str:
    if not raw:
        return "未知"
    return TYPE_LABELS.get(raw.lower(), raw)


def title_key(title: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", (title or "").lower())


def dedupe_results(results: list):
    """按 DOI（优先）或规范化标题合并重复记录；保留首次出现。

    返回 (去重后的列表, 合并条数)。DOI/标题相同通常意味着同一研究的不同版本或重复条目；
    合并后不应再被当作多份独立证据。两条记录都有 DOI 但不同，则视为不同研究，不合并。
    """
    seen_doi = set()
    seen_title = {}  # 规范化标题 -> 首次出现记录的 DOI（可能为空）
    unique = []
    dropped = 0
    for r in results:
        doi = (r.get("doi") or "").strip().lower()
        tk = title_key(r.get("title", ""))
        duplicate = False
        if doi and doi in seen_doi:
            duplicate = True
        elif tk and tk in seen_title:
            prev_doi = seen_title[tk]
            # 双方都有 DOI 且不同 -> 不同研究；否则视为同一研究的重复记录
            if not doi or not prev_doi or prev_doi == doi:
                duplicate = True
        if duplicate:
            dropped += 1
            continue
        if doi:
            seen_doi.add(doi)
        if tk:
            seen_title.setdefault(tk, doi)
        unique.append(r)
    return unique, dropped


def search_openalex(keyword: str, limit: int, mailto: str):
    q = urllib.parse.quote(keyword)
    url = f"https://api.openalex.org/works?search={q}&per-page={limit}&mailto={urllib.parse.quote(mailto)}"
    data = http_get_json(url)
    results = []
    for w in data.get("results", []):
        doi = norm_doi(w.get("doi") or "")
        authors = [
            clean_text((a.get("author") or {}).get("display_name", ""))
            for a in w.get("authorships", [])
            if (a.get("author") or {}).get("display_name")
        ]
        source = (w.get("primary_location") or {}).get("source") or {}
        journal = clean_text(source.get("display_name", ""))
        oa = w.get("open_access") or {}
        best = w.get("best_oa_location") or {}
        oa_pdf = best.get("pdf_url") or oa.get("oa_url") or ""
        results.append(
            {
                "title": clean_text(w.get("display_name", "")),
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
    title = clean_text((m.get("title") or [""])[0])
    authors = [
        clean_text(f"{a.get('given', '')} {a.get('family', '')}".strip())
        for a in m.get("author", [])
    ]
    year = None
    for key in ("published-print", "published-online", "issued"):
        dp = (m.get(key) or {}).get("date-parts") or []
        if dp and dp[0]:
            year = dp[0][0]
            break
    journal = clean_text((m.get("container-title") or [""])[0])
    return {
        "title": title,
        "authors": authors,
        "year": year,
        "journal": journal,
        "type": m.get("type") or "",
    }


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
    results, dropped = dedupe_results(results)
    outdir = args.output or "."
    os.makedirs(outdir, exist_ok=True)
    slug = slugify(args.keyword, 50)

    json_path = os.path.join(outdir, f"search_{slug}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    lines = [f"# 检索结果：{args.keyword}", ""]
    lines.append("> 以下为检索清单（摘要级线索），不是全文结论；同一 DOI/标题的重复记录已合并，合并后仍不等于独立研究。")
    if dropped:
        lines.append(f"> 本次按 DOI/标题合并重复记录 {dropped} 条。")
    lines.append("")
    for i, r in enumerate(results, 1):
        lines.append(f"## [{i}] {r['title']}")
        if r["authors"]:
            lines.append(f"- 作者：{', '.join(r['authors'])}")
        if r["year"]:
            lines.append(f"- 年份：{r['year']}")
        if r["journal"]:
            lines.append(f"- 期刊：{r['journal']}")
        if r.get("type"):
            lines.append(f"- 类型：{type_label(r['type'])}")
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
        meta = {"title": args.title or doi, "authors": [], "year": None, "journal": "", "type": ""}

    title = args.title or meta.get("title") or doi
    abstract = abstract_by_doi(doi)
    oa_pdf = "" if args.no_pdf else oa_pdf_url(doi, args.mailto)
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
    stype = type_label(meta.get("type"))
    lines.append(f"**来源类型**：{stype}")
    if stype == "综述":
        lines.append("**说明**：综述为二手来源，具体实验数据应回引原始研究。")

    pdf_path = None
    full_text = ""
    if oa_pdf:
        try:
            pdf_path = os.path.join(outdir, slug + ".pdf")
            download(oa_pdf, pdf_path)
            with open(pdf_path, "rb") as fh:
                head = fh.read(4)
            if head == b"%PDF":
                full_text = extract_pdf_text(pdf_path)
            else:
                os.remove(pdf_path)
                pdf_path = None
        except Exception:
            if pdf_path and os.path.exists(pdf_path):
                os.remove(pdf_path)
            pdf_path = None

    if full_text:
        evidence = "全文级（自动提取，未经人工核对；引用具体数据前核对原文）"
    elif abstract:
        evidence = "摘要级（仅摘要，未获取全文；不能据此推断实验细节、统计或对照）"
    else:
        evidence = "仅元数据（摘要与全文均未获取）"
    lines += ["", f"**证据级别**：{evidence}"]

    if abstract:
        lines += ["", "## 摘要", "", abstract]
    if full_text:
        lines += ["", "## 全文（自动提取）", "", full_text]

    if pdf_path is None and not args.no_pdf:
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
    g.add_argument("--no-pdf", action="store_true", help="只生成元数据+摘要的 md，不下载 PDF/全文")
    g.add_argument("--mailto", default=DEFAULT_MAILTO)
    g.set_defaults(func=cmd_get)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())

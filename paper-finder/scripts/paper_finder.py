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


def oa_locations(doi: str, mailto: str) -> dict:
    """返回开放获取位置：{"pdf": PDF 直链, "landing": 落地页/HTML 全文页}。

    网页版优先于 PDF：HTML 转出来的 Markdown 有段落和标题层级，比 PDF 抽文本干净。
    """
    out = {"pdf": "", "landing": ""}
    work = {}
    try:
        work = http_get_json(f"https://api.openalex.org/works/https://doi.org/{urllib.parse.quote(doi)}")
    except Exception:
        work = {}
    best = work.get("best_oa_location") or {}
    out["pdf"] = (best.get("pdf_url") or "").strip()
    out["landing"] = (best.get("landing_page_url") or "").strip()
    if not out["landing"]:
        oa_url = ((work.get("open_access") or {}).get("oa_url") or "").strip()
        if oa_url and not oa_url.lower().endswith(".pdf"):
            out["landing"] = oa_url
    if not out["pdf"]:
        try:
            u = http_get_json(
                f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi)}?email={urllib.parse.quote(mailto)}"
            )
            loc = u.get("best_oa_location") or {}
            out["pdf"] = (loc.get("url_for_pdf") or "").strip()
            out["landing"] = out["landing"] or (loc.get("url") or "").strip()
        except Exception:
            pass
    if not out["pdf"] and out["landing"].lower().endswith(".pdf"):
        out["pdf"], out["landing"] = out["landing"], ""
    return out


def oa_pdf_url(doi: str, mailto: str) -> str:
    return oa_locations(doi, mailto)["pdf"]


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
    # 最后一条路：poppler 的 pdftotext（makelatex 那套环境里通常已有）
    try:
        import shutil
        import subprocess

        exe = shutil.which("pdftotext")
        if exe:
            out = subprocess.run(
                [exe, "-layout", pdf_path, "-"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------- markwebdown

MARKWEBDOWN_WRAPPER = os.path.expanduser("~/.agents/skills/markwebdown/scripts/markwebdown")
MARKWEBDOWN_PY = os.path.expanduser("~/.agents/skills/markwebdown/scripts/fetch_md.py")
CRAWL4AI_PY = os.path.expanduser("~/AppData/Roaming/uv/tools/crawl4ai/Scripts/python.exe")


def _markwebdown_cmd() -> list:
    """优先直接用 crawl4ai 解释器跑 fetch_md.py，再退回 bash 启动器。

    Windows 上 shutil.which("bash") 会命中 C:\\Windows\\system32\\bash.EXE（WSL 存根），
    未安装 WSL 发行版时该命令必然失败且没有可读报错，故不能让它抢在最前面。
    """
    import shutil

    def _is_wsl_stub(path: str) -> bool:
        return bool(path) and "system32" in path.lower()

    if os.path.exists(CRAWL4AI_PY) and os.path.exists(MARKWEBDOWN_PY):
        return [CRAWL4AI_PY, MARKWEBDOWN_PY]
    explicit = os.environ.get("MARKWEBDOWN_BIN")
    if explicit:
        bash = shutil.which("bash")
        return [bash, explicit] if bash and not _is_wsl_stub(bash) else [explicit]
    bash = shutil.which("bash")
    if bash and not _is_wsl_stub(bash) and os.path.exists(MARKWEBDOWN_WRAPPER):
        return [bash, MARKWEBDOWN_WRAPPER]
    if os.path.exists(CRAWL4AI_PY) and os.path.exists(MARKWEBDOWN_PY):
        return [CRAWL4AI_PY, MARKWEBDOWN_PY]
    return []


def strip_frontmatter(text: str) -> dict:
    """拆 markwebdown 的 frontmatter，返回 (meta, body)。"""
    meta = {}
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            block = text[4:end]
            body = text[end + 4 :].lstrip("\n")
            for line in block.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip().strip('"')
    return meta, body


BOILERPLATE_HEADING = re.compile(
    r"^(your privacy|we use cookies|rights and permissions|about this article|"
    r"share this article|cite this article|subject|ethics declarations|additional information|search)",
    re.I,
)


def trim_web_boilerplate(text: str) -> str:
    """删掉出版社页面上的 cookie 横幅与尾部版权区块，保留正文/方法/数据可用性/参考文献。"""
    kept: list = []
    skip = False
    for line in text.splitlines():
        if line.startswith("## "):
            skip = bool(BOILERPLATE_HEADING.match(line[3:].strip()))
        if not skip:
            kept.append(line)
    return "\n".join(kept).strip()


def dsh_edge_cdp() -> str:
    """DSH 侧边栏浏览器（Edge/Chrome）的调试端口：端口随机，只能从 DevToolsActivePort 读。

    这样「侧边栏里认证过的会话」可以直接被 paper-finder 复用，不用另开窗口。
    """
    base = os.path.expanduser("~/AppData/Local/dsh-computer-use-win/agent-browser")
    try:
        names = os.listdir(base)
    except OSError:
        return ""
    dirs = [os.path.join(base, n) for n in names if os.path.isfile(os.path.join(base, n, "DevToolsActivePort"))]
    dirs.sort(key=lambda d: os.path.getmtime(os.path.join(d, "DevToolsActivePort")), reverse=True)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for d in dirs[:3]:
        try:
            with open(os.path.join(d, "DevToolsActivePort"), encoding="utf-8") as fh:
                port = int(fh.read().split()[0])
        except Exception:
            continue
        url = f"http://127.0.0.1:{port}"
        try:
            with opener.open(url + "/json/version", timeout=1.5) as resp:
                if resp.status == 200:
                    return url
        except Exception:
            continue
    return ""


def cdp_alive(port: int = 9222) -> str:
    """探测本地是否已有带调试端口的浏览器（用户登录过、过了人机验证）。"""
    import socket

    sock = socket.socket()
    sock.settimeout(0.3)
    try:
        sock.connect(("127.0.0.1", port))
        return f"http://127.0.0.1:{port}"
    except Exception:
        pass
    finally:
        sock.close()
    return dsh_edge_cdp()


def chrome_path(app: str = "edge") -> str:
    """返回浏览器可执行文件；默认 Edge（用户指定），可切 Chrome。"""
    import shutil

    if app == "edge":
        candidates = (
            os.environ.get("EDGE_PATH", ""),
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        )
        fallback = shutil.which("msedge") or ""
    else:
        candidates = (
            os.environ.get("CHROME_PATH", ""),
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
        )
        fallback = shutil.which("chrome") or ""
    for cand in candidates:
        if cand and os.path.exists(cand):
            return cand
    return fallback


def html_fulltext(landing: str, timeout: int = 180, cdp: str = "", tab: str = "") -> tuple:
    """用 markwebdown 把落地页抓成 Markdown，返回 (正文, 来源 URL, 说明)。"""
    import subprocess
    import tempfile

    cmd = _markwebdown_cmd()
    if not cmd or not landing:
        return "", "", "markwebdown 不可用"
    tmpdir = tempfile.mkdtemp(prefix="pf-web-")
    try:
        extra = ["--cdp", cdp] if cdp else []
        if cdp and tab:
            # 从已登录/已过验证的标签页直接读 DOM，避免重开页面再被 Cloudflare 拦
            extra += ["--tab", tab]
        proc = subprocess.run(
            cmd + [landing, "-o", tmpdir, "--json", "--timeout", "45000", *extra],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        raw = proc.stdout or ""
        start = raw.find("{")
        if start == -1:
            return "", "", (proc.stderr or "markwebdown 无输出").strip().splitlines()[-1][:120]
        summary = json.loads(raw[start:])
        items = summary.get("items") or []
        if not items or not items[0].get("ok") or not items[0].get("path"):
            err = (items[0].get("error") if items else "") or "抓取失败"
            return "", "", err[:120]
        path = items[0]["path"]
        if not os.path.isabs(path):
            path = os.path.join(tmpdir, path)
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        meta, body = strip_frontmatter(text)
        body = trim_web_boilerplate(body)
        return body, meta.get("final_url") or meta.get("source") or landing, ""
    except Exception as exc:
        return "", "", f"{type(exc).__name__}: {exc}"[:120]
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)


def looks_like_article(text: str) -> bool:
    """区分正文页和登录墙/摘要页：够长且有段落结构才算。"""
    if not text or len(text) < 2500:
        return False
    paragraphs = [ln for ln in text.splitlines() if len(ln.strip()) > 80]
    return len(paragraphs) >= 8


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
    loc = {"pdf": "", "landing": ""}
    if not args.no_pdf:
        try:
            loc = oa_locations(doi, args.mailto)
        except Exception:
            loc = {"pdf": "", "landing": ""}
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
    web_text = ""
    web_source = ""
    web_note = ""
    if not args.no_pdf and not args.no_web:
        landing = loc.get("landing") or f"https://doi.org/{doi}"
        # 优先级：手动 --cdp > DSH 侧边栏浏览器（已登录态）> 本地 9222 窗口
        dsh = dsh_edge_cdp()
        candidates = [c for c in (args.cdp, dsh, cdp_alive()) if c]
        candidates = list(dict.fromkeys(candidates))
        needles = f"{doi}|{title[:60]}" if candidates else ""
        web_text, web_source, web_note = "", "", ""
        # 先试「已开标签页直接读 DOM」（不重载，不会再次触发行验证），再退回重新打开
        for cdp in candidates:
            got, src, note = html_fulltext(
                landing, timeout=args.web_timeout, cdp=cdp, tab=needles
            )
            if got and looks_like_article(got):
                web_text, web_source = got, src
                web_note = ""
                break
            web_note = note or (f"标签页正文太短（{len(got)} 字符）" if got else "没有匹配的标签页")
        if not web_text and candidates:
            got, src, note = html_fulltext(
                landing, timeout=args.web_timeout, cdp=candidates[0], tab=""
            )
            if got and looks_like_article(got):
                web_text, web_source = got, src
            else:
                web_note = note or (f"网页正文太短（{len(got)} 字符）" if got else "抓取失败")
        if web_text and not looks_like_article(web_text):
            web_note = f"网页正文过短或无段落结构（{len(web_text)} 字符），改走 PDF"
            web_text = ""
        if not web_text and not candidates:
            web_note = web_note or "可能需要登录或人机验证"
            print(
                f"提示：该页可能需要登录/验证——先运行 `paper_finder.py open {doi}`，"
                "在弹出的浏览器里完成认证后重跑本命令。",
                flush=True,
            )
    if not web_text and loc.get("pdf"):
        try:
            pdf_path = os.path.join(outdir, slug + ".pdf")
            download(loc["pdf"], pdf_path)
            with open(pdf_path, "rb") as fh:
                head = fh.read(4)
            if head == b"%PDF":
                full_text = extract_pdf_text(pdf_path)
                if not full_text:
                    web_note = web_note or "PDF 已下载但抽不出文本（缺 pypdf/pdfplumber 且无 pdftotext），仅保留摘要"
            else:
                os.remove(pdf_path)
                pdf_path = None
        except Exception:
            if pdf_path and os.path.exists(pdf_path):
                os.remove(pdf_path)
            pdf_path = None

    if web_text:
        evidence = "全文级（网页版经 markwebdown 转换，未经人工核对；引用具体数据前核对原文）"
    elif full_text:
        evidence = "全文级（PDF 自动提取，未经人工核对；引用具体数据前核对原文）"
    elif abstract:
        evidence = "摘要级（仅摘要，未获取全文；不能据此推断实验细节、统计或对照）"
    else:
        evidence = "仅元数据（摘要与全文均未获取）"
    lines += ["", f"**证据级别**：{evidence}"]
    if web_note:
        lines += ["", f"**全文获取**：{web_note}"]

    if abstract:
        lines += ["", "## 摘要", "", abstract]
    if web_text:
        lines += ["", "## 全文（网页版）", "", f"> 来源：{web_source}", "", web_text]
    elif full_text:
        lines += ["", "## 全文（自动提取）", "", full_text]

    if not web_text and not full_text and not args.no_pdf:
        lines += [
            "",
            "## 下载",
            "",
            f"未找到可自动获取的开放获取全文，请访问 DOI 链接手动下载：https://doi.org/{doi}",
        ]

    md_path = os.path.join(outdir, slug + ".md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"MD: {md_path}")
    if pdf_path:
        print(f"PDF: {pdf_path}")
    else:
        print(f"未自动下载 PDF：https://doi.org/{doi}")


def cmd_open(args):
    import subprocess

    if args.url:
        url = args.url
    elif args.doi:
        url = f"https://doi.org/{norm_doi(args.doi)}"
    else:
        print("需要 DOI 或 --url", file=sys.stderr)
        return 1
    chrome = chrome_path(args.app)
    if not chrome:
        print("找不到浏览器，请设置 EDGE_PATH / CHROME_PATH 环境变量", file=sys.stderr)
        return 1
    profile = os.path.expanduser(f"~/.paper-finder/{args.app}-profile")
    os.makedirs(profile, exist_ok=True)
    subprocess.Popen(
        [
            chrome,
            "--remote-debugging-port=9222",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            url,
        ],
        close_fds=True,
    )
    print(f"已打开浏览器（CDP 9222）：{url}")
    print("完成登录 / 人机验证后，重跑 get 命令，会自动接管这个窗口取全文。")
    return 0


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
    g.add_argument("--no-web", action="store_true", help="不用 markwebdown 抓网页全文，只走 PDF")
    g.add_argument("--web-timeout", type=int, default=180, help="网页全文抓取超时秒数（默认 180）")
    g.add_argument("--cdp", default=None, help="接管已开浏览器，如 http://127.0.0.1:9222（默认自动探测）")
    g.add_argument("--mailto", default=DEFAULT_MAILTO)
    g.set_defaults(func=cmd_get)

    o = sub.add_parser("open", help="打开带调试端口的浏览器，用于付费墙登录/人机验证")
    o.add_argument("doi", nargs="?", default=None)
    o.add_argument("--url", default=None)
    o.add_argument("--app", choices=["edge", "chrome"], default="edge", help="用哪个浏览器（默认 edge）")
    o.set_defaults(func=cmd_open)

    args = ap.parse_args()
    result = args.func(args)
    sys.exit(result or 0)


if __name__ == "__main__":
    sys.exit(main())

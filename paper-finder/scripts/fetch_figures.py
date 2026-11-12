#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fetch figure images from publisher pages via an already-authenticated CDP browser.

Usage:
    python fetch_figures.py 10.1021/ar800130s -o ./文献
    python fetch_figures.py --list dois.txt -o ./文献 --min-width-cm 8

Design notes:
  * Reuses paper-finder's CDP discovery (same port as `paper_finder.py open`).
  * Publisher-specific URL rules recover the largest available asset:
        ACS      : strip the "/m_" prefix of the CDN path -> full-resolution PNG
        Wiley    : only the "-m" (medium) asset is exposed
        Elsevier : "-grN.jpg", small (served at ~470-600 px)
        RSC      : body figures are usually not exposed as <img>
  * Every panel is measured; panels below --min-width-cm at 300 dpi are flagged.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paper_finder as pf  # noqa: E402

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36")

PUBLISHER_RULES = {
    "acs": {
        "match": "acs.silverchair-cdn.com",
        "note": "去掉路径中的 /m_ 前缀即可获得原图（ACS 全分辨率）",
    },
    "wiley": {
        "match": "onlinelibrary.wiley.com/cms/asset",
        "note": "仅暴露 -m（medium）资源，约 1000 px 宽",
    },
    "elsevier": {
        "match": "ars.els-cdn.com",
        "note": "grN 小图，约 470–600 px；_lrg 变体多数期刊不存在",
    },
    "rsc": {
        "match": "rscj.silverchair-cdn.com",
        "note": "正文图通常不以 <img> 暴露，需人工补",
    },
}


# ---------------------------------------------------------------- CDP plumbing
class Tab:
    """Minimal CDP page handle (no external deps, uses native WebSocket via Node)."""

    def __init__(self, cdp: str):
        self.cdp = cdp.rstrip("/")

    def _get(self, path: str, method: str = "GET"):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(self.cdp + path, method=method)
        with opener.open(req, timeout=15) as r:
            body = r.read().decode("utf-8", "replace")
        try:
            return json.loads(body)
        except Exception:
            return body

    def find_tab(self, needle: str):
        try:
            tabs = self._get("/json/list")
        except Exception:
            return None
        for t in tabs:
            if t.get("type") != "page":
                continue
            hay = (t.get("url", "") + " " + t.get("title", "")).lower()
            if needle.lower() in hay:
                return t
        return None

    def open_tab(self, url: str):
        return self._get("/json/new?" + urllib.parse.quote(url, safe=""), "PUT")

    def close_tab(self, tid: str):
        try:
            self._get(f"/json/close/{tid}")
        except Exception:
            pass


def evaluate(cdp: str, target_id: str, expression: str, timeout: int = 30):
    """Run JS in a tab via a short Node helper. The script is written to a temp file
    because multi-line expressions do not survive being passed as a single argv item."""
    node = _node_bin()
    if not node:
        raise RuntimeError("未找到 node，可用 --no-cdp 直接按 URL 推断")
    helper = os.path.join(HERE, "_cdp_eval.cjs")
    _ensure_helper(helper)
    import subprocess
    import tempfile

    fd, js_path = tempfile.mkstemp(prefix="pf-js-", suffix=".js")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(expression)
        p = subprocess.run([node, helper, cdp, target_id, "--file", js_path],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout + 10)
    finally:
        try:
            os.remove(js_path)
        except OSError:
            pass
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "cdp eval failed")[:300])
    return p.stdout


def _node_bin() -> str:
    cand = os.environ.get("NODE_BIN", "")
    if cand and os.path.exists(cand):
        return cand
    import shutil
    for name in ("node", "node.exe"):
        w = shutil.which(name)
        if w:
            return w
    base = os.path.expanduser("~/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/node/bin/node.exe")
    return base if os.path.exists(base) else ""


def _ensure_helper(path: str) -> None:
    if os.path.exists(path):
        return
    io.open(path, "w", encoding="utf-8").write(r"""
const fs = require("node:fs");
const [,, cdp, tid, flag, file] = process.argv;
let expr = process.argv[5] || "";
if (flag === "--file" && file) expr = fs.readFileSync(file, "utf-8");
(async () => {
  const list = await (await fetch(cdp + "/json/list")).json();
  const t = list.find(x => x.id === tid) || list.find(x => x.type === "page");
  if (!t) { console.error("no tab"); process.exit(2); }
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let id = 0; const pend = new Map();
  ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } };
  const send = (method, params = {}) => new Promise((res, rej) => {
    const i = ++id; pend.set(i, m => m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result));
    ws.send(JSON.stringify({ id: i, method, params }));
    setTimeout(() => { if (pend.has(i)) { pend.delete(i); rej(new Error("timeout")); } }, 30000);
  });
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true });
  if (r.exceptionDetails) { console.error("JS: " + (r.exceptionDetails.text || "")); process.exit(3); }
  process.stdout.write(r.result && r.result.value != null ? String(r.result.value) : "");
  ws.close();
})().catch(e => { console.error(e.message); process.exit(1); });
""".strip())


def wait_ready(cdp: str, target_id: str, timeout: int = 75, poll: int = 3) -> dict:
    """Poll until the tab shows a real article (title not a challenge page and has images)."""
    import time as _t

    deadline = _t.time() + timeout
    last = {}
    while _t.time() < deadline:
        try:
            raw = evaluate(cdp, target_id,
                           "JSON.stringify({t:document.title,r:document.readyState,"
                           "n:document.images.length,u:location.href})")
            last = json.loads(raw or "{}")
        except Exception:
            last = {}
        title = last.get("t", "") or ""
        blocked = re.search(r"Just a moment|请稍候|安全验证|Are you a robot|Attention Required", title, re.I)
        if not blocked and last.get("r") == "complete" and last.get("n", 0) >= 3:
            return last
        _t.sleep(poll)
    return last


# ---------------------------------------------------------------- page scraping
IMG_JS = r"""(() => {
  const out = [], seen = new Set();
  const generic = /^\s*(Details are in the caption|Refer to the image caption|Graphic\.|Figure \d+\. Refer)/i;
  const capOf = (im) => {
    // 1) 最近的 figcaption
    let el = im;
    for (let i = 0; i < 6 && el; i++) {
      const fc = el.querySelector ? el.querySelector('figcaption') : null;
      if (fc && fc.innerText && fc.innerText.trim().length > 10) return fc.innerText.trim();
      el = el.parentElement;
    }
    // 2) 兄弟/父节点里 class 含 caption 的块
    let node = im.parentElement;
    for (let i = 0; i < 5 && node; i++) {
      const cand = Array.from(node.querySelectorAll('[class*="caption"],[id*="caption"]'))
        .find(e => e.innerText && e.innerText.trim().length > 10);
      if (cand) return cand.innerText.trim();
      node = node.parentElement;
    }
    // 3) 图片后面的短段落
    const sib = im.closest('figure,div');
    if (sib) {
      const p = Array.from(sib.querySelectorAll('p')).find(e => e.innerText && e.innerText.trim().length > 20);
      if (p) return p.innerText.trim();
    }
    return '';
  };
  Array.from(document.querySelectorAll('img')).forEach(im => {
    const src = im.currentSrc || im.src || '';
    if (!src || src.startsWith('data:') || seen.has(src)) return;
    const w = im.naturalWidth || 0, h = im.naturalHeight || 0;
    if (w < 200 || h < 120) return;
    seen.add(src);
    let alt = (im.alt || '').trim();
    if (generic.test(alt)) alt = '';
    let cap = '';
    try { cap = capOf(im); } catch (e) { cap = ''; }
    if (generic.test(cap)) cap = '';
    out.push({ src: src, alt: alt.slice(0, 160), cap: cap.slice(0, 300), w: w, h: h });
  });
  return JSON.stringify({ title: document.title, url: location.href, images: out });
})()"""


JUNK = re.compile(r"logo|cover|badge|icon|spinner|avatar|banner|advert|scite|chorus|orcid|"
                  r"crossref|share|social|figure-viewer", re.I)


def clean_caption(s: str) -> str:
    """去掉出版社界面文字（figure viewer / PowerPoint 等），并压成一行。"""
    if not s:
        return ""
    s = re.sub(r"(?i)open in figure viewer|view large|download to slide|powerpoint|"
               r"view full size|full size image|download\s*:?\s*download[^.]*", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^Figure\s*\d+[\.:]?\s*", "", s)
    # 去掉版权/授权尾巴
    s = re.split(r"\s*(?:Adapted with permission|Reproduced with permission|"
                 r"Copyright ©|Copyright \()", s)[0]
    return s.strip(" .;:·-")


def publisher_of(url: str) -> str:
    for name, rule in PUBLISHER_RULES.items():
        if rule["match"] in url:
            return name
    return "other"


def figure_no(img: dict):
    m = re.search(r"Figure\s*(\d+)", img.get("alt", ""))
    if m:
        return int(m.group(1))
    m = re.search(r"-fig-0*(\d+)-", img.get("src", ""))
    if m:
        return int(m.group(1))
    m = re.search(r"-gr0*(\d+)\.", img.get("src", ""))
    if m:
        return int(m.group(1))
    m = re.search(r"_0*(\d{2,3})\.(png|jpe?g|gif|tif)", img.get("src", ""))
    if m:
        return int(m.group(1))
    return None


def best_url(src: str) -> tuple:
    """Return (url_to_fetch, note) applying publisher rules."""
    if "silverchair-cdn.com" in src and "/m_" in src:
        return src.replace("/m_", "/"), "已切换为原图"
    return src, ""


def fetch_bytes(url: str, timeout: int = 45) -> bytes:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://pubs.acs.org/"})
    with opener.open(req, timeout=timeout) as r:
        return r.read()


def measure(path: str):
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return (0, 0)


# ---------------------------------------------------------------- main routine
def collect(doi: str, outdir: str, min_cm: float = 8.0, dry: bool = False, cdp: str = "",
            numbered_only: bool = False) -> dict:
    doi = pf.norm_doi(doi)
    key = re.sub(r"[^A-Za-z0-9]+", "-", doi).strip("-")[:60]
    src_dir = os.path.join(outdir, "figs", "src")
    os.makedirs(src_dir, exist_ok=True)

    cdp = cdp or pf.cdp_alive(9222)
    if not cdp:
        raise RuntimeError("没有可用的调试端口浏览器；先运行 paper_finder.py open <DOI>")

    tab = Tab(cdp)
    url = "https://doi.org/" + doi
    target = tab.find_tab(doi) or tab.find_tab(doi.split("/")[-1])
    if not target:
        # ACS/RSC 的 URL 不含 DOI，只能靠标题匹配
        try:
            probe = re.sub(r"[^0-9A-Za-z\u4e00-\u9fa5 ]", "",
                           pf.crossref_meta(doi).get("title", ""))[:40].strip()
        except Exception:
            probe = ""
        if probe:
            target = tab.find_tab(probe)
    opened = False
    if not target:
        target = tab.open_tab(url)
        opened = True
    wait_ready(cdp, target["id"], timeout=75)

    try:
        wait_ready(cdp, target["id"], timeout=30)
        raw = evaluate(cdp, target["id"], IMG_JS)
        data = json.loads(raw or "{}")
    except Exception as e:
        if opened:
            tab.close_tab(target["id"])
        raise RuntimeError(f"读取页面失败：{e}")

    imgs = [i for i in data.get("images", []) if not JUNK.search(i["src"] + i["alt"])]

    # 去重：同图号保留像素面积最大的一张；无图号的单独收集
    by_no, extra = {}, []
    for img in imgs:
        no = figure_no(img)
        area = img.get("w", 0) * img.get("h", 0)
        if no is None:
            extra.append(img)
            continue
        if no not in by_no or area > by_no[no].get("w", 0) * by_no[no].get("h", 0):
            by_no[no] = img

    items = [(no, by_no[no]) for no in sorted(by_no)]
    if not numbered_only:
        items += [(None, img) for img in extra]

    records = []
    seq = 0
    for no, img in items:
        src = img["src"]
        pub = publisher_of(src)
        tag = f"fig{no:02d}" if no is not None else None
        if tag is None:
            seq += 1
            tag = f"img{seq:02d}"
        if dry:
            records.append({"fig": no, "tag": tag, "url": src, "publisher": pub,
                            "px": f"{img.get('w', 0)}x{img.get('h', 0)}",
                            "alt": (lambda c: c[:300] + ("…" if len(c) > 300 else ""))(clean_caption(img.get("cap") or img.get("alt") or "")), "note": "dry-run"})
            continue
        dest_url, note = best_url(src)
        data_bytes = None
        if dest_url != src:
            try:
                data_bytes = fetch_bytes(dest_url)
                if len(data_bytes) < 20000:
                    data_bytes = None
            except Exception:
                data_bytes = None
        if data_bytes is None:
            try:
                data_bytes = fetch_bytes(src)
            except Exception as e:
                records.append({"fig": no, "tag": tag, "url": src, "publisher": pub,
                                "error": str(e)[:80]})
                continue
        ext = ".png" if ".png" in (dest_url if data_bytes else src).lower() else ".jpg"
        path = os.path.join(src_dir, f"{key}_{tag}{ext}")
        io.open(path, "wb").write(data_bytes)
        w, h = measure(path)
        records.append({
            "fig": no, "tag": tag, "url": dest_url, "publisher": pub,
            "file": os.path.relpath(path, outdir),
            "px": f"{w}x{h}", "print_cm": round(w / 300 * 2.54, 1) if w else 0,
            "ok": bool(w and (w / 300 * 2.54) >= min_cm),
            "alt": (lambda c: c[:300] + ("…" if len(c) > 300 else ""))(clean_caption(img.get("cap") or img.get("alt") or "")),
            "note": note or PUBLISHER_RULES.get(pub, {}).get("note", ""),
        })

    manifest = os.path.join(src_dir, "_manifest.json")
    old = []
    if os.path.exists(manifest):
        try:
            old = json.load(io.open(manifest, encoding="utf-8"))
        except Exception:
            old = []
    old = [r for r in old if r.get("doi") != doi]
    old.append({"doi": doi, "key": key, "title": data.get("title", ""),
                "page": data.get("url", url), "min_width_cm": min_cm, "figures": records})
    io.open(manifest, "w", encoding="utf-8").write(json.dumps(old, ensure_ascii=False, indent=1))

    if opened:
        tab.close_tab(target["id"])
    return {"doi": doi, "key": key, "figures": records}


WRITE_HEAD = "## 插图"


def find_md_for_doi(outdir: str, doi: str):
    """在输出目录里按 frontmatter 的 doi 找到对应的文献 md。"""
    target = pf.norm_doi(doi).lower()
    for root, dirs, files in os.walk(outdir):
        dirs[:] = [d for d in dirs if d not in ("figs", "_raw", ".git")]
        for name in files:
            if not name.endswith(".md"):
                continue
            p = os.path.join(root, name)
            try:
                head = io.open(p, encoding="utf-8", errors="replace").read(4000)
            except OSError:
                continue
            m = re.search(r"^doi:\s*(\S+)", head, re.M)
            if not m:
                continue
            if pf.norm_doi(m.group(1).strip().strip('"').strip("'")).lower() == target:
                return p
    return None


def write_back(doi: str, outdir: str, records: list, title: str = "") -> str:
    """把已下载的图作为「## 插图」一节回填到该文献的 md；返回 md 路径或空串。"""
    md = find_md_for_doi(outdir, doi)
    if not md:
        return ""
    md_dir = os.path.dirname(md)
    lines = [WRITE_HEAD, ""]
    n = 0
    for r in records:
        if r.get("error") or not r.get("file"):
            continue
        n += 1
        rel = os.path.relpath(os.path.join(outdir, r["file"]), md_dir).replace("\\", "/")
        if r.get("fig"):
            label = f"图 {r['fig']}"
        else:
            label = f"插图 {n}"
        alt = (r.get("alt") or "").strip()
        caption = f"{label}：{alt}" if alt else label
        lines.append(f"![{caption}]({rel})")
        lines.append("")
    if n == 0:
        return ""

    text = io.open(md, encoding="utf-8").read()
    block = "\n".join(lines).rstrip() + "\n"
    # 已有插图节则整体替换
    if re.search(r"^## 插图\s*$", text, re.M):
        text = re.sub(r"^## 插图\s*$.*?(?=^## |\Z)", block + "\n", text, flags=re.M | re.S)
    elif re.search(r"^## 参考文献\s*$", text, re.M):
        text = re.sub(r"^## 参考文献\s*$", block + "\n## 参考文献", text, count=1, flags=re.M)
    else:
        text = text.rstrip() + "\n\n" + block
    io.open(md, "w", encoding="utf-8").write(text)
    return md


def main():
    ap = argparse.ArgumentParser(prog="fetch_figures.py", description="按 DOI 抓取论文插图")
    ap.add_argument("doi", nargs="?", help="单个 DOI")
    ap.add_argument("--list", default=None, help="DOI 列表文件（每行一个）")
    ap.add_argument("-o", "--output", default=".")
    ap.add_argument("--min-width-cm", type=float, default=8.0,
                    help="300 dpi 下可印宽度的合格线（默认 8 cm），低于此值标记为不合格")
    ap.add_argument("--dry-run", action="store_true", help="只列出候选图，不下载")
    ap.add_argument("--cdp", default="", help="显式指定 CDP 地址，默认自动探测")
    ap.add_argument("--write-back", action="store_true",
                    help="下载后把图作为「## 插图」一节回填到该文献的 md")
    ap.add_argument("--numbered-only", action="store_true",
                    help="只取能识别出图号的图（组图用），默认取全部非垃圾图")
    a = ap.parse_args()

    dois = [a.doi] if a.doi else []
    if a.list:
        dois += [l.strip() for l in io.open(a.list, encoding="utf-8") if l.strip()
                 and not l.startswith("#")]
    if not dois:
        ap.error("需要 DOI 或 --list 文件")

    total_ok = total = 0
    for doi in dois:
        try:
            res = collect(doi, a.output, a.min_width_cm, a.dry_run, a.cdp, a.numbered_only)
        except Exception as e:
            print(f"[FAIL] {doi}: {e}")
            continue
        figs = res["figures"]
        ok = [f for f in figs if f.get("ok")]
        total += len(figs); total_ok += len(ok)
        print(f"[{doi}] {len(figs)} 张，合格 {len(ok)} 张")
        for f in figs:
            flag = "✓" if f.get("ok") else ("·" if f.get("px") else "?")
            tag = f.get("tag") or ("fig%02d" % f["fig"] if f.get("fig") else "img")
            extra = f.get("px", "") + (f"  {f.get('print_cm')} cm" if f.get("print_cm") else "")
            print(f"   {flag} {tag:<8} {f.get('publisher',''):<9} {extra:<16} {f.get('note','')}")
        if a.write_back and not a.dry_run:
            md = write_back(doi, a.output, figs, res.get("title", ""))
            print(f"   回填：{os.path.relpath(md, a.output) if md else '未找到对应文献 md（先跑 get 生成）'}")
    if not a.dry_run:
        print(f"\n合计 {total} 张，达到 {a.min_width_cm} cm 合格线的 {total_ok} 张")
        print("清单：figs/src/_manifest.json")


if __name__ == "__main__":
    main()

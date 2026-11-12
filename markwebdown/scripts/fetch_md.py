#!/usr/bin/env python
"""markwebdown — 把网页抓成干净的 Markdown 文件。

用法：
    python fetch_md.py <url> [<url> ...] [-o DIR] [--raw] [--chrome] [--json]

默认：headless 内置浏览器 + 正文过滤（省 token），每个 URL 落一个 .md，
带 frontmatter（source/title/fetched/status）。失败不中断其余 URL。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

os.environ.setdefault("CRAWL4AI_NO_CLOUD_NOTICE", "1")  # 关掉 stderr 广告位

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode  # noqa: E402
from crawl4ai.content_filter_strategy_lxml import PruningContentFilterLXML  # noqa: E402
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator  # noqa: E402

BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass
class Item:
    url: str
    ok: bool
    path: Path | None = None
    title: str = ""
    chars: int = 0
    ratio: float = 0.0
    error: str = ""
    note: str = ""
    final_url: str = ""


def slugify(text: str, fallback: str = "index") -> str:
    text = BAD_CHARS.sub("-", text).strip(" .-")
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return (text[:80] or fallback).lower()


def target_path(out_dir: Path, url: str, title: str) -> Path:
    parsed = urlparse(url)
    host = slugify(parsed.netloc.replace("www.", ""), "site")
    path = parsed.path.rstrip("/")
    last = slugify(path.split("/")[-1], "")
    stem = "index" if not path or path == "/" else (last or slugify(title, "") or "page")
    if parsed.query:
        stem += "-" + slugify(parsed.query, "")[:24]
    return out_dir / host / f"{stem}.md"


def frontmatter(item: Item, url: str, fetched: str) -> str:
    safe = lambda v: str(v).replace('"', "'").replace("\n", " ")
    lines = [
        "---",
        f"source: {url}",
        f'title: "{safe(item.title)}"',
        f"fetched: {fetched}",
        f"chars: {item.chars}",
    ]
    if item.final_url and item.final_url.rstrip("/") != url.rstrip("/"):
        lines.append(f"final_url: {item.final_url}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def _junk_line(line: str) -> bool:
    """表格布局站点在整页模式下的边框/图片行，去掉不影响正文。"""
    s = line.strip()
    if not s:
        return False
    if "![" in s:  # 纯图片行（含图片链接包裹）
        return True
    if not s.startswith("|"):
        return False
    if not re.sub(r"[|\-:\s]", "", s):  # | --- |
        return True
    return len(re.findall(r"\w", s, re.UNICODE)) < 10


def clean_raw(text: str) -> str:
    kept = [ln for ln in text.splitlines() if not _junk_line(ln)]
    out: list[str] = []
    blanks = 0
    for ln in kept:
        if ln.strip():
            blanks = 0
            out.append(ln.rstrip())
        else:
            blanks += 1
            if blanks <= 1:
                out.append("")
    return "\n".join(out).strip()


def choose_body(raw: str, fit: str, want_raw: bool) -> tuple[str, str]:
    """决定用哪一版正文。

    过滤后的 fit_markdown 在表格布局页面上会把所有段落并成一行，压缩率好看但
    不可读。行数明显塌陷时宁可回退整页（清理掉边框残留），保住段落结构。
    """
    if want_raw:
        return clean_raw(raw), ""
    if not fit:
        return clean_raw(raw), "无过滤结果，用整页"

    raw_lines = len([ln for ln in raw.splitlines() if ln.strip()])
    fit_lines = len([ln for ln in fit.splitlines() if ln.strip()])
    if raw_lines >= 20 and fit_lines < raw_lines * 0.4:
        return clean_raw(raw), f"过滤把段落并成 {fit_lines} 行（整页 {raw_lines} 行），已回退整页保结构"
    return fit, ""


def build_configs(args: argparse.Namespace) -> tuple[BrowserConfig, CrawlerRunConfig]:
    browser_kwargs: dict = {
        "headless": not args.headed,
        "verbose": False,
        "chrome_channel": "chrome" if args.chrome else "chromium",
    }
    if args.cdp:
        # 接管一个已经打开的浏览器（用户先在里面登录/过验证），不用自己发浏览器
        browser_kwargs["cdp_url"] = args.cdp
    elif args.profile:
        browser_kwargs["user_data_dir"] = str(Path(args.profile).expanduser())
    proxy = args.proxy or os.environ.get("MARKWEBDOWN_PROXY", "")
    if args.direct:
        # 走校园网/本机直连：Chrome 默认读系统代理，这里显式关掉
        browser_kwargs["extra_args"] = ["--no-proxy-server"]
    elif proxy:
        browser_kwargs["proxy"] = proxy
    browser_cfg = BrowserConfig(**browser_kwargs)
    run_kwargs: dict = {
        "cache_mode": CacheMode.ENABLED if args.cache else CacheMode.BYPASS,
        "page_timeout": args.timeout,
    }
    if args.wait_for:
        run_kwargs["wait_for"] = args.wait_for
    if args.wait_ms:
        # 有些页面统计脚本晚到，多等一会儿再取正文
        run_kwargs["delay_before_return_html"] = args.wait_ms / 1000
    if not args.raw:
        run_kwargs["markdown_generator"] = DefaultMarkdownGenerator(
            content_filter=PruningContentFilterLXML()
        )
    return browser_cfg, CrawlerRunConfig(**run_kwargs)


def grab_tab(cdp: str, needle: str) -> tuple:
    """从已打开的标签页里取 DOM（不导航、不刷新），返回 (html, url, title, error)。"""
    import shutil
    import subprocess
    import tempfile

    node = shutil.which("node")
    script = Path(__file__).with_name("cdp_dom.mjs")
    if not node:
        return "", "", "", "找不到 node"
    fd, html_path = tempfile.mkstemp(prefix="mw-tab-", suffix=".html")
    os.close(fd)
    try:
        proc = subprocess.run(
            [node, str(script), cdp, needle, html_path],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        )
        info = {}
        for line in (proc.stdout or "").strip().splitlines()[::-1]:
            if line.startswith("{"):
                info = json.loads(line)
                break
        if not info.get("ok"):
            return "", "", "", (info.get("error") or (proc.stderr or "取 DOM 失败").strip().splitlines()[-1])[:160]
        with open(html_path, encoding="utf-8", errors="replace") as fh:
            html = fh.read()
        return html, info.get("url", ""), info.get("title", ""), ""
    except Exception as exc:
        return "", "", "", f"{type(exc).__name__}: {exc}"[:160]
    finally:
        try:
            os.remove(html_path)
        except OSError:
            pass


async def run_tab(args: argparse.Namespace, urls: list[str], out_dir: Path) -> int:
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

    t0 = time.time()
    fetched_at = time.strftime("%Y-%m-%d %H:%M:%S")
    items: list[Item] = []
    gen = DefaultMarkdownGenerator(content_filter=None if args.raw else PruningContentFilterLXML())
    for url in urls:
        needle = args.tab or url
        html, final_url, title, err = grab_tab(args.cdp, needle)
        item = Item(url=url, ok=not err)
        if err:
            item.error = err
            items.append(item)
            continue
        res = gen.generate_markdown(input_html=html, base_url=final_url or url)
        raw = getattr(res, "raw_markdown", "") or ""
        fit = getattr(res, "fit_markdown", "") or ""
        item.title = title or ""
        item.final_url = final_url or url
        body, note = choose_body(raw, fit, args.raw)
        item.chars = len(body)
        item.ratio = 100 * (1 - len(fit) / len(raw)) if raw and fit else 0.0
        item.note = (note + "；" if note else "") + "从已打开标签页读取（未重新下载）"
        item.path = target_path(out_dir, url, item.title)
        item.path.parent.mkdir(parents=True, exist_ok=True)
        item.path.write_text(frontmatter(item, url, fetched_at) + body + "\n", encoding="utf-8")
        items.append(item)

    emit(items, time.time() - t0, args.json)
    return 0 if any(i.ok for i in items) else 1


async def run(args: argparse.Namespace) -> int:
    urls = list(dict.fromkeys(args.urls))  # 去重保序
    out_dir = Path(args.out).expanduser()

    if args.tab:
        if not args.cdp:
            print("--tab 需要配合 --cdp 使用（从已打开的浏览器里读 DOM）", file=sys.stderr)
            return 2
        return await run_tab(args, urls, out_dir)

    browser_cfg, run_cfg = build_configs(args)

    items: list[Item] = []
    t0 = time.time()
    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        results = await crawler.arun_many(
            urls, config=run_cfg, max_concurrency=max(1, args.concurrency)
        )

    fetched_at = time.strftime("%Y-%m-%d %H:%M:%S")
    # arun_many 的结果顺序不保证与入参一致，按 result.url 对齐，取不到再退回顺序
    by_url = {}
    for res in results:
        res_url = getattr(res, "url", None) or getattr(res, "redirected_final_url", None)
        if res_url:
            by_url[str(res_url)] = res
            by_url.setdefault(str(res_url).rstrip("/"), res)

    ordered = [by_url.get(u) or by_url.get(u.rstrip("/")) for u in urls]
    if any(r is None for r in ordered):
        ordered = list(results)

    for url, result in zip(urls, ordered):
        item = Item(url=url, ok=bool(result.success))
        if not result.success:
            lines = [ln.strip() for ln in (result.error_message or "").splitlines() if ln.strip()]
            key = next(
                (ln for ln in lines if "Timeout" in ln or "net::ERR" in ln or "ERR_" in ln),
                next((ln for ln in lines if ln.startswith("Error:")), lines[-1] if lines else "unknown error"),
            )
            item.error = key[:200]
            items.append(item)
            continue

        md = result.markdown
        raw = (getattr(md, "raw_markdown", "") or "") if md else ""
        fit = (getattr(md, "fit_markdown", "") or "") if md else ""
        body, note = choose_body(raw, fit, args.raw)
        item.title = str((result.metadata or {}).get("title") or "").strip()
        item.final_url = str(
            getattr(result, "redirected_url", None) or getattr(result, "url", "") or ""
        )
        item.chars = len(body)
        item.ratio = 100 * (1 - len(fit) / len(raw)) if raw and fit else 0.0
        item.note = note

        item.path = target_path(out_dir, url, item.title)
        item.path.parent.mkdir(parents=True, exist_ok=True)
        item.path.write_text(
            frontmatter(item, url, fetched_at) + body + "\n", encoding="utf-8"
        )
        items.append(item)

    dt = time.time() - t0
    emit(items, dt, args.json)
    return 0 if any(i.ok for i in items) else 1


def emit(items: list[Item], dt: float, as_json: bool) -> None:
    ok_items = [i for i in items if i.ok]
    if as_json:
        print(json.dumps(
            {
                "ok": len(ok_items),
                "total": len(items),
                "seconds": round(dt, 1),
                "items": [
                    {
                        "url": i.url,
                        "ok": i.ok,
                        "path": str(i.path) if i.path else None,
                        "title": i.title,
                        "chars": i.chars,
                        "final_url": i.final_url or i.url,
                        "ratio": round(i.ratio, 1),
                        "note": i.note,
                        "error": i.error,
                    }
                    for i in items
                ],
            },
            ensure_ascii=False,
            indent=2,
        ))
    else:
        for i in items:
            if i.ok:
                print(f"[ok] {i.url}\n     -> {i.path}  ({i.chars} 字符，正文压缩 {i.ratio:.0f}%)")
                if i.note:
                    print(f"     !  {i.note}")
            else:
                print(f"[fail] {i.url}\n       {i.error}")
        print(f"\n{len(ok_items)}/{len(items)} 成功，共 {dt:.1f}s")


def main() -> int:
    parser = argparse.ArgumentParser(description="网页转 Markdown（crawl4ai 封装）")
    parser.add_argument("urls", nargs="+", help="一个或多个 URL")
    parser.add_argument("-o", "--out", default="./web-md", help="输出目录（默认 ./web-md）")
    parser.add_argument("--raw", action="store_true", help="不过滤正文，保留整页")
    parser.add_argument("--cache", action="store_true", help="命中本地缓存（重抓同一页时更快，但可能缺 fit_markdown）")
    parser.add_argument("--chrome", action="store_true", help="用系统 Chrome 而不是内置 headless shell")
    parser.add_argument("--concurrency", type=int, default=3, help="并发数（默认 3）")
    parser.add_argument("--timeout", type=int, default=45000, help="单页超时毫秒（默认 45000）")
    parser.add_argument("--wait-for", default=None, help="等待 CSS 选择器出现后再取内容")
    parser.add_argument("--wait-ms", type=int, default=0, help="取正文前额外等待毫秒")
    parser.add_argument("--headed", action="store_true", help="显示浏览器窗口（登录/过反爬时用）")
    parser.add_argument("--profile", default=None, help="持久化浏览器配置目录，登录态可复用")
    parser.add_argument("--cdp", default=None, help="接管已开浏览器，如 http://127.0.0.1:9222（登录态复用）")
    parser.add_argument("--tab", default=None, help="从已开标签页读 DOM（需 --cdp；值为 URL/标题子串，多个用 | 分隔）")
    parser.add_argument("--direct", action="store_true", help="绕过系统代理直连（校园网 IP 访问出版社时用）")
    parser.add_argument("--proxy", default=None, help="浏览器代理，如 http://127.0.0.1:7897（也可用 MARKWEBDOWN_PROXY）")
    parser.add_argument("--json", action="store_true", help="输出机器可读的 JSON 摘要")
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())

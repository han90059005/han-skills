---
name: markwebdown
description: 把网页抓成干净的 Markdown 文件（批量、去导航/广告、带 frontmatter）。用本地 crawl4ai + 无头浏览器渲染，适合 JS 页面、正文提取、批量存资料、给 RAG/笔记备料。触发词：「markwebdown」「抓网页」「网页转 Markdown」「存成 md」「把这几个链接抓下来」「批量抓取」「扒一下这个站」。
---

# markwebdown

网页 → Markdown 落盘。底层是本地 `crawl4ai`（uv tool 环境，已装好），默认无头浏览器渲染 + 正文过滤。

## 先判要不要用

| 情况 | 用什么 |
|---|---|
| 公开静态页、只要读一下 | 直接用 `web_fetch`，不必进浏览器 |
| JS 渲染 / 要正文清洗 / 批量 / 要落盘 | **本 skill** |
| 要登录、要点击、要截图 | DSH 自带浏览器工具 |

原则：`web_fetch` 拿得到就不要开浏览器，一个浏览器页比一次 HTTP 贵 10 倍以上。

## 用法

```bash
# 单个
bash scripts/markwebdown https://www.python.org/

# 批量 + 指定目录
bash scripts/markwebdown https://a.com/doc1 https://a.com/doc2 -o ./web-md

# 保留整页（不过滤正文）
bash scripts/markwebdown https://example.com --raw

# 等页面渲染出某个元素再取（SPA 常用）
bash scripts/markwebdown https://spa.site/page --wait-for ".article-body" --wait-ms 1500

# 用系统 Chrome（内置浏览器有兼容问题时的备选）
bash scripts/markwebdown https://example.com --chrome

# 站点要走代理才通
bash scripts/markwebdown https://example.com --proxy http://127.0.0.1:7897

# 机器可读摘要
bash scripts/markwebdown https://example.com --json
```

脚本里可直接用绝对路径：
`C:\Users\admin\.agents\skills\markwebdown\scripts\markwebdown`

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `urls` | 必填 | 多个 URL，自动去重 |
| `-o, --out` | `./web-md` | 输出目录 |
| `--raw` | 关 | 不过滤，保留整页 Markdown |
| `--chrome` | 关 | 用系统 Chrome 而非内置 headless shell |
| `--proxy` | 无 | 浏览器代理，如 `http://127.0.0.1:7897`；也可用 `MARKWEBDOWN_PROXY` |
| `--cache` | 关 | 命中本地缓存（快，但可能缺 `fit_markdown`） |
| `--concurrency` | 3 | 并发数 |
| `--timeout` | 45000 | 单页超时（毫秒） |
| `--wait-for` | 无 | 等 CSS 选择器出现 |
| `--wait-ms` | 0 | 取正文前额外等待 |
| `--json` | 关 | JSON 摘要 |

## 输出

```
web-md/
└── python.org/
    └── index.md
```

每份带 frontmatter：

```markdown
---
source: https://www.python.org/
title: "Welcome to Python.org"
fetched: 2026-10-30 16:20:11
chars: 4470
---
```

正文默认是压缩后的 `fit_markdown`（实测比整页少约 75% 的字符），这就是省 token 的关键。
要整页细节（链接、表格、侧栏）就用 `--raw`。

失败不会中断其余 URL，结束会打印 `[fail] <url>` 和原因；`--json` 里同样有 `error` 字段。

**结构保护**：表格布局的站点（如 paulgraham.com）正文过滤会把所有段落并成一行，脚本检测到行数塌陷（<整页的 40%）会自动回退整页并清掉边框残留，同时在输出里打一行 `! 过滤把段落并成 N 行…`。所以看到这行不是出错，是它在保段落。

## 深爬整个站

脚本只管给 URL 抓单页。要顺着链接爬整站，用 crawl4ai 自带 CLI：

```bash
crwl https://docs.site.com --deep-crawl bfs --max-pages 10 -o md
```

## 登录态页面

不要为了登录去配 browser-use。crawl4ai 自带 profile 机制：

```bash
crwl browser --url https://site.com    # 手动登录，存 profile
crwl profiles                          # 列出已有 profile
bash scripts/markwebdown <url> ...     # 抓取时用保存好的 cookie/profile
```

## 登录态 / 付费墙 / 反爬

普通爬取走内置无头浏览器；遇到 Cloudflare 人机验证或付费墙，无头模式一定被拦，换成「真人窗口 + 接管」：

```bash
# 1. 开一个带调试端口的可见浏览器（在窗口里登录 / 过验证 / 校园网认证）
"/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" \
  --remote-debugging-port=9222 \
  --user-data-dir="%USERPROFILE%\.paper-finder\edge-profile" \
  --new-window "https://pubs.acs.org/doi/10.1021/<DOI>"

# 2a. 首选：从已经打开的标签页读 DOM（不重新导航，不会二次触发验证）
bash scripts/markwebdown <同一个 URL> --cdp http://127.0.0.1:9222 \
  --tab "10.1021/acs.macromol.8b02071|论文标题片段" -o ./web-md

# 2b. 备选：接管浏览器重新打开（会重新走一遍页面加载）
bash scripts/markwebdown <同一个 URL> --cdp http://127.0.0.1:9222 -o ./web-md
```

`--tab` 做的是：用 Node 连 CDP，找到 URL/标题匹配的标签页，`Runtime.evaluate` 取
`document.documentElement.outerHTML`，再用 crawl4ai 的 markdown 生成器离线转（不再联网、不开新页）。
匹配串支持多个候选，用 `|` 分隔。

相关参数：

| 参数 | 用途 |
|---|---|
| `--cdp URL` | 接管已在跑的浏览器（登录态、已过验证） |
| `--tab 子串` | 从已开标签页读 DOM；配合 `--cdp`，不重导航 |
| `--direct` | 绕过系统代理直连；校园网 IP 访问出版社时必须用，走代理会丢校园 IP |
| `--profile DIR` | 持久化浏览器配置，下次免登录 |
| `--headed` | 显示窗口（一般和 `--profile` 配合，首次登录用） |

注意：`--direct` 只关浏览器自己的代理；如果系统代理开着，其他程序的请求仍走代理。

实测：ACS 付费墙文章（10.1021/acs.macromol.8b02071），Edge 可见窗口过验证后 `--tab` 读出 55k–62k 字符全文；
同一页用无头浏览器直连则稳定返回 `Blocked by anti-bot protection: Cloudflare JS challenge`。

## 已知坑

- **很多文档站自带 `.md` 版本**：Vue、Vite 这类站点页面里会写「Are you an LLM? Read `/xxx.md`」。先试 `web_fetch <url>.md`，命中就别开浏览器。
- **部分站点在当前网络不通或超时**：实测 `developer.mozilla.org`（Chrome 里 45s 超时，curl 却 200）、`news.ycombinator.com`、`crawl4ai.com`。这类不是脚本问题，换域名/换节点，或用 `--proxy` 显式指定。
- 正文过滤会保留少量导航行（如 "Menu / On this page"），需要绝对干净时用 `--raw` 自己裁。
- 内置 `crawl4ai-doctor` 只测 `crawl4ai.com`，在本机会误报失败；要用自检脚本：
  `C:\Users\admin\AppData\Roaming\uv\tools\crawl4ai\Scripts\python.exe D:\AI-tools\crawl4ai\healthcheck.py`
- 首次调用会起浏览器，约 2–3 秒；批量时这个开销会被摊薄。
- 抓带登录/付费内容的站点前先确认对方 ToS；不要用 `--raw` 之外的参数去绕。

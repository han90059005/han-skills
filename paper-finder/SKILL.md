---
name: paper-finder
description: "按关键词检索学术文献，返回经校验的标题、作者、期刊、年份、DOI 与摘要；标注来源类型（原始研究/综述/预印本）与证据级别（摘要级/全文级），按 DOI/标题合并重复记录。人工筛选后可按分类下载 PDF，生成 Markdown 内容备份（元数据+摘要+开放获取全文），并可抓取原文插图（含出版社取图规则与分辨率判定）。用于校园网环境下的论文查找、筛选与整理；不负责谷歌学术抓取。"
metadata:
  short-description: 关键词查文献、分类下载 PDF 并生成 MD 备份
---

# paper-finder

用于「关键词 → 文献清单 → 人工筛选 → 分类下载 PDF + Markdown 内容备份」的文献整理流程。检索和元数据来自 OpenAlex、Crossref、Unpaywall、Semantic Scholar，标题与 DOI 以权威来源为准。

## 使用前必须确认（缺一就向用户询问）

每次使用先确认这三项，用户没给的必须主动询问，不要用默认值硬猜：

1. **关键词**：检索什么
2. **分类名**：下载后的子文件夹名（通常用户给关键词时一起给，不必预先定义分类体系）
3. **存放目录**：结果、PDF 和 MD 存到哪里（第一次问，之后可复用）

用户只给了关键词时，先回一句补齐信息，例如：

> 请告诉我：分类名、存放目录；如果已有默认存放目录也可以直接说。

## 工作流

### 1. 检索

```bash
python scripts/paper_finder.py search "关键词" -o 输出目录 --limit 20
```

在输出目录生成两个文件：

- `search_<关键词>.md`：给人看的结果清单（标题 / 作者 / 年份 / 期刊 / 类型 / DOI / OA 链接 / 摘要），顶部标注摘要级边界与本次合并的重复条数
- `search_<关键词>.json`：给机器用的原始数据（已按 DOI/标题去重），供后续 `get` 批量处理

把 `search_*.md` 给用户，由用户人工筛选并指定每篇的分类。

### 2. 下载 + 备份

对用户选中的每一篇执行：

```bash
python scripts/paper_finder.py get DOI -o 输出目录 --category 分类名
```

脚本会：

1. 用 Crossref 按 DOI 校验标题、作者、期刊、年份
2. 补摘要（OpenAlex / Semantic Scholar）
3. 找开放获取位置（OpenAlex / Unpaywall），先拿 HTML 落地页
4. **用 markwebdown 把落地页抓成 Markdown 全文**（正文 / 方法 / 数据可用性 / 参考文献都在，结构比 PDF 抽取干净）；网页正文过短（登录墙、只有摘要页）时自动退回 PDF 抽取
5. 生成 `输出目录/<分类>/<标题>.md`，内容 = 元数据 + 来源类型 + 证据级别 + 摘要 + 全文（网页版优先）
6. 两种全文都拿不到时，在 MD 里写入 DOI 链接供手动下载

全文来源会写进 md：`## 全文（网页版）` 段前有 `> 来源：<最终 URL>`（DOI 跳转后的出版社地址），
证据级别相应写成「全文级（网页版经 markwebdown 转换…）」或「全文级（PDF 自动提取…）」。

需要关闭网页抓取时加 `--no-web`（只走 PDF），或 `--web-timeout` 调整单页超时（默认 180s）。

### 3. 取图（写综述、做汇报图时用）

```bash
python scripts/fetch_figures.py 10.1021/xxx -o 输出目录                  # 取全部非垃圾图
python scripts/fetch_figures.py 10.1021/xxx -o 输出目录 --numbered-only  # 只取能识别图号的
python scripts/fetch_figures.py 10.1021/xxx -o 输出目录 --write-back     # 取图并回填到文献 md
python scripts/fetch_figures.py --list dois.txt -o 输出目录              # 批量
python scripts/fetch_figures.py 10.1021/xxx -o 输出目录 --dry-run        # 只列候选
```

**三种用法，按需选一种**

| 场景 | 命令 | 结果 |
|---|---|---|
| 只想看看有哪些图 | `--dry-run` | 仅打印候选，不落盘 |
| 做组图（要已知图号） | `--numbered-only` | 只保存 `Figure N` 可识别的图，命名 `figNN` |
| 给文献 md 配图 | `--write-back` | 取全部非垃圾图，并在该文献 md 里插入 `## 插图` 一节 |

不指定时**默认取全部非垃圾图**（垃圾图判定：logo / cover / badge / icon / spinner / scite / crossref / share 等）。无法识别图号的图命名 `imgNN`，图号在图清单里留空。

**回填规则**（`--write-back`）

- 按 frontmatter 的 `doi:` 在输出目录里找到对应文献 md；
- 生成 `## 插图` 一节，每张图一行 `![图 N：<图注>](../figs/src/....jpg)`；
- 已有 `## 插图` 则整体替换（可重复执行），否则插到 `## 参考文献` 之前；
- 找不到文献 md 时提示「先跑 `get`」，不报错。

**图注从 DOM 抓取**，并清洗出版社界面文字（`Open in figure viewer`、`PowerPoint`、`View Large`、`Download to Slide`）与版权尾巴（`Adapted with permission`、`Reproduced with permission`、`Copyright (c)`）。拿不到时退回 `alt`。

**产出**

- `figs/src/<doi-key>_<tag>.<ext>`
- `figs/src/_manifest.json`：每图的 DOI、图号、tag、出版社、像素、300 dpi 可印宽度、是否合格、图注

**出版社实测**（2026-11，校园网 + CDP 浏览器，同一批 DOI 逐家验证）

| 出版社 | 取图规则 | 实测最大 | 300 dpi 可印宽 | 结论 |
|---|---|---|---|---|
| ACS | CDN 路径去掉 `/m_` 前缀即得原图 | 5907×4782 | 50.0 cm | ✅ 首选 |
| Wiley | `-fig-000N-m.jpg`，只暴露 medium | 1167 px | 9.9 cm | ✅ 可用（≥8 cm） |
| Elsevier | `-grN.jpg`；`_lrg` / `.tif` / `?wid=` 全部 404 或被忽略 | 678 px | 5.7 cm | ⚠ 低于阈值，建议自绘 |
| RSC | 正文图不经 `<img>` 暴露（走独立图查看器） | — | — | ❌ 需人工补 |

**分辨率判定**：`--min-width-cm` 默认 8.0，规则是 `px / 300 * 2.54 < 阈值 → 不合格`。输出里 `✓` 合格、`·` 不合格。**不合格的图不要直接拼进正式文档**。

**版权与用途**：仅用于个人学习、课程作业与内部研究；进入正式文档必须逐图标注出处；不得再分发或用于对外发表。

**已知坑**（改代码前先看这几条）

1. `document.images` 是 HTMLCollection，没有 `forEach`，必须 `Array.from(document.querySelectorAll('img'))`。
2. 多行 JS 经命令行参数传给 node 会变成空返回，要写临时文件再读（脚本已处理）。
3. ACS / RSC 的正文 URL **不含 DOI**，标签页匹配会自动回退到 Crossref 标题；匹配不上就会新开标签，等于重新过一次 Cloudflare。
4. RSC 域名 `rscj.silverchair-cdn.com` 与 ACS 的 `acs.silverchair-cdn.com` 都含 `silverchair-cdn.com`，出版社判定必须用完整主机名。
5. Wiley 的图注容器里混着界面按钮文字，必须过 `clean_caption`；否则回填进 md 的图注是「Open in figure viewer」。

## 证据边界（配合 makepaper）

- `search_*.md` 只是线索清单：摘要级，不等于全文结论；摘要缺失时不要靠标题推断内容。
- `get` 生成的 md 会写明 **来源类型**（期刊论文 / 综述 / 预印本…）与 **证据级别**（摘要级 / 全文级），makepaper 按此判断能引用到多深。
- 来源类型取自 OpenAlex / Crossref 的 `type` 字段，综述与预印本的识别并不总是可靠；拿不准时按标题、摘要和 DOI 关系人工判断。
- 全文级来自自动提取，可能有 OCR/版式错误；引用具体数值、条件或公式前核对原文。
- 同一 DOI / 标题的重复记录由脚本合并；但「综述 + 原始研究」是两篇不同文献，不是重复——具体数据要回引原始研究。
- 新闻稿、机构网页、公众号等不是本脚本来源；若另用网页补充，按 makepaper 规则算二手，不计独立证据。

## 关键约定

- **链接正确性**：DOI 链接统一用 `https://doi.org/<DOI>` 构造，避免不稳定的出版社深链；标题在 `get` 阶段用 Crossref 二次校验。
- **MD 备份粒度（方案 B）**：元数据 + 摘要 + 能拿到的全文（网页版优先，PDF 兜底）。
- **网页全文依赖 markwebdown 技能**：缺它或缺 crawl4ai 时自动退回 PDF 抽取，不报错；`MARKWEBDOWN_BIN` 可指定自定义路径。
- **代理会毁掉校园网权限**：本机 Clash 在 7897 上时，出版社看到的是境外 IP，付费墙会误判。paper-finder 自己的 API 请求本来就直连；浏览器端要么 `--direct`，要么走下面的 CDP 登录态。
- **付费墙 / 人机验证的解法**（Cloudflare 无头必挂，校园网 IP 也挡不住）：

  ```bash
  paper_finder.py open 10.1021/xxx              # 弹出可见 Edge 窗口（CDP 9222）
  # 在窗口里完成登录 / 校园网认证 / 人机验证，等标题变成论文标题
  paper_finder.py get 10.1021/xxx -o 目录 --category 分类
  ```

  `open --app chrome` 可换 Chrome；`--app edge` 是默认。
  `get` 不需要手动传端口，按这个顺序自动找可用浏览器：

  1. `--cdp <url>` 显式指定；
  2. DSH agent 浏览器（端口随机，从 `%LOCALAPPDATA%\dsh-computer-use-win\agent-browser\*/DevToolsActivePort` 读）；
  3. 本地 `9222`（`open` 开的窗口）。

  找到浏览器后**先读已打开的标签页 DOM**（`markwebdown --tab`，URL/标题子串匹配）：不重新导航，就不会二次触发 Cloudflare。
  没有匹配标签或正文太短，才退回「接管浏览器重新打开」。

  实测（Clash 关闭、校园网出口 IP 113.140.3.79）：

  - 无头浏览器 + 直连/代理 → 全部被 Cloudflare Turnstile 拦；
  - `open` 弹出可见窗口 → 自动过验证；
  - Edge 标签页读 DOM：Macromolecules 一篇 **61,541 字符**，Experimental Section / Results / References 齐全；
  - 同一篇用 Chrome 窗口走爬取：59,670 字符。两条都对，路径不同。

  登录态与 Cloudflare 通过状态存在 `~/.paper-finder/edge-profile`（Chrome 是 `chrome-profile`），下次 `open` 通常不用再验证。

- **不要指望 DSH 界面里的网页面板**：聊天界面里嵌的那个浏览器是 WebView2，没有调试端口，脚本读不到、也复用它里面的登录；只能在 `open` 弹出的独立窗口里认证。
- **出版社页面常见问题**：cookie 横幅、尾部版权区块会被脚本自动剪掉；但付费墙页面只会拿到摘要，此时证据级别仍是「摘要级」，不要当成全文。
- **分类**：由用户指定，`--category` 决定子目录；不给分类时落到 `未分类/`。
- **重复合并**：`search` 默认按 DOI（优先）或规范化标题合并重复记录，只保留首次出现，并在清单顶部报告合并条数；合并后的 JSON 也只含唯一记录。
- **网络**：脚本内部已用 `ProxyHandler({})` 直连，绕过本机 Clash 代理；不要在代理失败时反复重试，直接报告。

## 常用分类建议（供参考，用户可自定义）

柔性电子 / 电子皮肤、高分子力化学、RAFT 可控聚合、硫族元素高分子、高分子接枝、表征分析、综述、未分类。

## 注意事项

- 免费 API 有频率限制，批量下载时按顺序处理、失败即记录后继续，不要并行狂刷。
- 反爬或订阅制文章拿不到 PDF 是正常情况，返回 DOI 链接让用户用校园网浏览器手动下载即可。
- 摘要缺失或被数据库截断时，只登记元数据，不要用标题推测研究结论。
- PDF 全文提取依赖 Python 的 `pypdf` 或 `pdfplumber`，缺失时只写元数据 + 摘要，不报错。

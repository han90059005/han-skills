# 🧰 han-skills

个人常用 Codex 技能库，长期维护、持续更新。

一套面向 [Codex](https://openai.com/codex) 场景的个人技能（Skills）集合，覆盖文档排版、文献管理、科研绘图与数据处理、演示文稿、开发与技能管理等方向，当前共 **17 个技能**。

---

## 🚀 快速开始

```powershell
# 1. 克隆仓库
git clone https://github.com/han90059005/han-skills.git

# 2. 按需把技能复制到本地技能目录
Copy-Item -Path "han-skills\mineru" `
          -Destination "$env:USERPROFILE\.agents\skills\mineru" `
          -Recurse -Force
```

> 本地技能目录通常是 `C:\Users\<你的用户名>\.agents\skills`。一次只装需要的即可，装上后新开一个对话就能用自然语言触发。

## 📦 技能总览

按「素材 → 库 → 内容 → 成品」四层组织：素材层（paper-finder、mineru、pptx、course-review-generator）产出 Markdown，makelibrary 建索引，内容层（makepaper、makenote）合成文稿，成品层（makelatex 出 PDF、makedocx 出 Word、makeppt 出汇报）负责排版；git-use、find-skills、skill-vetter、uv-python-runner、dir 等为工具与维护层。

## 📚 技能详情

### 📝 文档排版与笔记

#### course-review-generator

从课程 PPT（PDF）生成结构化复习笔记，或把多份已有的复习笔记/学习指南合并去重为一份 Markdown。支持扫描版 PDF 的视觉回读，可输出 Markdown 并可选转 PDF。

- **触发**：整理 PPT 复习资料 / 合并复习笔记 / 生成复习清单
- **相关**：内容生成后的排版交给 [makelatex](#makelatex)（PDF）或 [makedocx](#makedocx)（Word）

#### makenote

交互式维护 Markdown：学习笔记模式随对话增量维护（自动维护记忆快照），实验报告模式读 Excel 数据驱动更新报告、检测矛盾，交互补写分析。

- **触发**：/makenote / 做笔记 / 更新实验报告 / 加数据
- **相关**：批量生成复习资料用 [course-review-generator](#course-review-generator)

#### makepaper

读取文献 Markdown，合成带 `[n]` 角标引用的高质量中文论文/综述，输出可直接交给 makelatex 的 Markdown。

- **触发**：依据 md 资料写论文 / 综述
- **相关**：排版用 [makelatex](#makelatex)（PDF）或 [makedocx](#makedocx)（Word）

#### makelatex

把含 `[n]` 交叉引用的 Markdown 转成中文 PDF（XeLaTeX + ctex）：引用自动编号并链接到文末文献表，列表、表格、公式、代码块、图片按 Markdown 语义还原，可选目录与 PDF 书签；自动多遍编译，失败时保留日志并定位到第一个错误的行号。

- **触发**：Markdown 转 PDF / 含引用的文档排版 / 实验报告出 PDF
- **依赖**：TeX Live（xelatex）；字体在 `windows` 与 `fandol` 间自动回退

#### makedocx

把 Markdown / LaTeX / XeLaTeX 转成符合中文论文规范的 Word，字体、标题字号、1.5 倍行距、三线表、公式、参考文献一步到位。

- **触发**：md/tex 转 docx / 三线表 / 论文排版
- **依赖**：pandoc + python-docx（无需 TeX Live）

### 📚 文献与 PDF

#### paper-finder

按关键词检索学术文献，校验元数据，分类下载开放获取 PDF，并生成 Markdown 内容备份。

- **触发**：查文献 / 下载 PDF
- **依赖**：校园网环境

#### zotero-paper-reader

从 Zotero 文献库读取和分析论文，自动搜索、转 Markdown 并保存到 Notes/PaperInMarkdown。

- **触发**：Zotero / 读论文
- **依赖**：Zotero Desktop 本地 API（localhost:23119）

#### mineru

PDF / 课件 / 扫描件 → Markdown，并按需阅读、审校公式。两条路径：文字层文档秒级直读（quickread），复杂或扫描文档走 MinerU 4.0 转换（自动选 basic / standard 档）；转换后强制剥离 base64 图片，阅读前先出结构摘要、由用户确认范围，避免烧掉大量 token。

- **触发**：读 PDF / 快速看看这篇讲什么 / 课件转笔记 / 提取文献公式 / 扫描件能不能转
- **依赖**：MinerU 4.0 本地环境（`D:\AI-tools\mineru`，Python 3.12 + 模型约 2.55 GB）
- **注意**：与 MinerU 官方 `mineru` skill 同名，两者不要同时安装

#### makelibrary

扫描文献 md 目录，按标签词表打标签并生成集中索引（JSON + 可读清单，清单按标签统计篇数）。读一遍原文；内容层之后按标签筛选、只读命中的文件。

- **触发**：文献库 / 打标签 / 建立索引
- **依赖**：本地运行，不联网

### 🔬 科研与数据

#### gpc-plot

解析 Agilent（Cirrus 软件）GPC 数据文件，绘制 EPS+TIF 色谱图；支持单文件、多曲线叠加、批量出图。

- **触发**：GPC / 色谱图 / SEC / 分子量分布
- **依赖**：matplotlib + numpy

### 🎬 演示文稿

#### makeppt

把一个 Markdown 文件（实验报告/论文/大纲等）转成汇报 PPT，同时输出 PDF（LaTeX Beamer，默认 NWPU 模板）和可编辑 .pptx。先出提纲给用户审查，通过后智能提炼成逐页要点；文字颜色 ≤ 3 种、每页有页码、清晰可读。

- **触发**：makeppt / 生成PPT / md转PPT / 做汇报PPT
- **依赖**：TeX Live（xelatex）+ python-pptx
- **相关**：演示文稿的「输出层」；内容生成用 [makepaper](#makepaper) / [makenote](#makenote)

#### pptx

创建、读取、编辑 `.pptx` 文件：文本提取、模板与版式、演讲者备注、批注、合并与拆分等。

- **触发**：PPT / slides / presentation / .pptx 文件

### 🛠️ 开发与技能管理

#### git-use

本地项目与 GitHub 仓库互传：克隆、初始化后推送、令牌认证、`.gitignore` 与敏感信息检查，并涵盖本机实测故障（schannel→OpenSSL、代理、凭据管理器卡住、dubious ownership）。

- **触发**：git / github / push / clone / 上传

#### find-skills

发现并安装可用的 Agent 技能，回答"我怎么做 X""有没有能……的技能"类问题。

- **触发**：我怎么做 X / 找一个技能

#### skill-vetter

安装技能前的安全审查：检查危险标志、权限范围、可疑模式。

- **触发**：安装技能前审查

#### uv-python-runner

在 uv 管理的 Python 环境中执行脚本，处理中文路径、特殊字符文件名、依赖安装等。

- **触发**：uv run / pip 失败 / externally-managed-environment

#### dir

把一个目录打包成结构化 prompt，用于从零生成目录/项目骨架，或审查、优化已有目录；尊重 `.gitignore`，支持行号与 Markdown/XML 输出。

- **触发**：生成目录 / 优化目录 / 把目录转成 prompt

## 🧱 环境依赖

| 依赖 | 用途 | 说明 |
| --- | --- | --- |
| Python 3.12 + MinerU 4.0 | mineru | 独立环境 `D:\AI-tools\mineru`，模型 `D:\AI-tools\mineru-home` |
| Python + uv | gpc-plot、makeppt（python-pptx）等 | 系统自带 Python 3.9/3.12 或 uv 均可 |
| pandoc ≥ 3.0 | course-review-generator、makedocx | 安装于 `C:\Program Files\Pandoc` |
| TeX Live（xelatex） | makelatex、pandoc 出 PDF | 完整版安装于 `D:\AI-tools\latex\texlive\2026` |
| Zotero Desktop | zotero-paper-reader | 需开启本地 API |
| matplotlib + numpy | gpc-plot | 系统 Python 或 `uv run --with` |

## 🗂️ 目录结构

```text
han-skills/
├── course-review-generator/
├── dir/
├── find-skills/
├── git-use/
├── gpc-plot/
├── makelatex/
├── makelibrary/
├── makenote/
├── makepaper/
├── makeppt/
├── makedocx/
├── paper-finder/
├── mineru/
├── pptx/
├── skill-vetter/
├── uv-python-runner/
└── zotero-paper-reader/
```

## 🔄 维护约定

- **新增技能**：复制到本仓库根目录，并按分类同步更新「技能总览」和「技能详情」。
- **修改技能**：同步更新对应详情、触发词与描述。

## 📋 示例工作流：小作业速成链

适用于「查文献 → 写论文 → 出 PDF」的课程小论文、综述或读书报告。

```text
作业目录/
├── literature/        ← 文献摘要 md（paper-finder 生成）
└── 论文.md / 论文.pdf  ← makepaper → makelatex 的产物
```

1. **检索文献**（paper-finder）：按关键词检索并导出清单。

```powershell
py C:\Users\admin\.agents\skills\paper-finder\scripts\paper_finder.py search "关键词" -o literature --limit 20
```

打开 `literature\search_关键词.md`，筛选想要的文献并记下 DOI。

2. **保存摘要**（paper-finder，只存摘要、不下全文）：对每篇选中的文献执行——

```powershell
py C:\Users\admin\.agents\skills\paper-finder\scripts\paper_finder.py get <DOI> -o literature --category 分类 --no-pdf
```

生成的 md 以 `## 摘要` 标记，makepaper 能直接识别为「摘要级」来源。

3. **合成论文**（makepaper）：让 Codex 读取 `literature` 里的 md，按题目要求写中文论文，输出 `论文.md`（带 `[n]` 角标引用）。

4. **生成 PDF**（makelatex）：

```powershell
py C:\Users\admin\.agents\skills\makelatex\scripts\md_to_latex_pdf.py 论文.md -o 作业目录
```

生成 `论文.pdf`，检查正文角标与文末参考文献。

> 定位：摘要级引用，适合综述型小作业；需要深挖方法/数据时，第 2 步去掉 `--no-pdf` 下载全文，再用 mineru 转全文。

## 📝 更新日志

### 2026-10-26

- `mineru` 按实战反馈优化（4 份高分子物理课件、292 页实测）：
  - 新增**路径 A+**：文字层课件（PPT 转 PDF、讲义）默认走「`quickread` 秒读全文 + 公式页定点 `render` 核对」，不再把「抽公式、转笔记」等同于全量 MinerU；`probe` 现在按页数算出「约 N 分钟」提示性价比，`quickread` 截断提示改为指向 `--save` + `read` 分段。
  - 环境常量补 `$env:PYTHONIOENCODING="utf-8"`：中文路径乱码实测只有它管用，`[Console]::OutputEncoding` 无效。
  - `render` 的临时核对输出改到 `$env:TEMP\pdfcheck`，用完即删，不再往课件/资料目录丢 `_pages/`。
  - 档位实测表新增「292 页 / 未跑 / 约 2 h 不值」，并写明「页数 × 25 s，超 20 页先考虑 A+」；补齐两条坑：页数以 `probe` 为准（`pdftotext` 尾部多一页空壳）、`quickread` 抽出的公式只当线索（常数项会丢）。

### 2026-10-24

- `makelatex` 重构（参考文献引擎 + 还原 Markdown 结构）：
  - 参考文献改用 `thebibliography` + `\cite`，编号由 LaTeX 维护，正文角标随之同步；新增 `--bib-sort` 按首次引用顺序重排（GB/T 7714 顺序编码制）；生成时检查「引用了不存在的编号 / 文献未被引用 / 顺序不对」并提示。
  - 列表、表格、围栏代码块、`>` 引用块、`[文字](url)` 链接、独立成行的图片按 Markdown 语义还原（此前会压成流水句、表格变竖线文本）。
  - 编译改为自动多遍（按 `.aux` 是否稳定 + 日志 `Rerun` 决定），中间产物进 `build/` 后拷回；失败保留日志并打印 `文件:行号` 首条错误。
  - 标题默认自动编号并写入 PDF 书签；文档里只要有一处标题自带编号就整体改为不编号，杜绝「0.1 子标题」这类错号。
  - 新增 `--toc`（点线目录）、`--fontset auto|windows|fandol|mac`、`--keep-log`、`--verbose`；页码移到页脚居中，标题/作者写入 PDF 元数据。
  - 图片按 md 所在目录解析，跨目录时复制到 `assets/`；图片缺失画占位框，不再中断编译。
- README 移除「技能总览」里的 Mermaid 流程图，改为一句四层说明（维护成本高于收益）。
- 新增 `mineru` 技能：PDF / 课件 / 扫描件转 Markdown 的完整流水线。先探测文字层决定档位（basic / standard），转换后强制剥离 base64 图片，阅读前必须出结构摘要并由用户确认范围，避免一次性烧掉上下文。含 `quickread`（秒级直读）、`render`（页面渲图供视觉核对）、`mathreview`（只抽公式并标记可疑项）。
- 移除 `pdf-reader`：文字层秒级抽取与页面渲染两项能力已并入 `mineru`，其独立 venv 与依赖未安装的 OCR 脚本一并废弃。

### 2026-10-20

- 新增 `makeppt` 技能：把一个 Markdown 文件转成汇报 PPT，同时输出 PDF（LaTeX Beamer，NWPU 模板）和可编辑 .pptx；先出提纲给用户审查，通过后智能提炼成逐页要点。定位为演示文稿的「输出层」。
- 新增 `dir` 技能：把一个目录打包成结构化 prompt，用于从零生成目录/项目骨架，或审查、优化已有目录；内置纯标准库的 `snapshot.py`（尊重 .gitignore、UTF-8、Markdown/XML 输出）。

### 2026-10-19

- gpc-plot：修复表格色条不跟随 --line-color 的问题，支持单物质同色绘制。

### 2026-10-16

- 新增 `git-use` 技能：本地与 GitHub 互传的完整流程。
- 合并技能：删除 `three-line-table-docx`（功能并入 `makedocx`）；将 `multi-source-review-consolidator` 并入 `course-review-generator`。
- 重命名：`md-latex-to-docx` → `pandoc-docx` → `makedocx`。
- 为笔记类技能写清各自侧重点，避免互相抢任务。
- 重写 README：分类总览、触发词、安装指引、环境依赖与目录结构。
- 本地技能目录直连 GitHub，更新统一经 GitHub 同步（单仓库工作流）。
- `paper-finder` 新增 `--no-pdf`：只存 `## 摘要`，不下载全文。
- `makelatex` 从 Tectonic 切换到 TeX Live 的 `xelatex`。
- 安装完整 TeX Live 2026 于 `D:\AI-tools\latex\texlive\2026` 并加入 PATH。
- README 新增「小作业速成链」示例工作流。
- 技能总览从表格改为横向流程图（Paper / Note / Skill 三条生成主线）。
- `pandoc-docx` 重命名为 `makedocx`，与 makepaper / makelatex / makenote 命名对齐。
- 内容层（makepaper、makenote）新增「输入接口（归一化）」；成品层（makelatex、makedocx）新增「运行可靠性」。
- 新增 `makelibrary`：文献 md 打标签 + 生成集中索引；makepaper 增加按标签筛选的阅读检索入口与低/高强度机制。
- 将 `raft-report-updater` 并入 `makenote`（成为其「模式二：实验报告」），脚本迁至 `makenote/scripts/`。
- 流程图改为四层流水线：素材 → 库（makelibrary）→ 内容 → 成品。


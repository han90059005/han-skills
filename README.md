# han-skills

保存个人常用 Codex skill，长期更新。当前共收录 17 个技能，涵盖文档排版、文献管理、科研绘图与数据处理、演示文稿、以及技能与 Git 管理等方向。

## 技能总览

| 技能 | 一句话说明 |
| --- | --- |
| [course-review-generator](#course-review-generator) | 从课程 PPT（PDF）生成结构化复习笔记 |
| [find-skills](#find-skills) | 发现并安装可用的 Agent 技能 |
| [git-use](#git-use) | 连接本地项目与 GitHub 并上传（push） |
| [gpc-plot](#gpc-plot) | 绘制高分子 GPC/SEC 色谱图 |
| [makelatex](#makelatex) | 带交叉引用的 Markdown 转中文 LaTeX PDF |
| [makenote](#makenote) | 围绕一份 Markdown 文件的笔记构建助手 |
| [makepaper](#makepaper) | 依据 Markdown 资料合成带引用的中文论文 |
| [md-latex-to-docx](#md-latex-to-docx) | Markdown/LaTeX 转符合中文论文规范的 Word |
| [multi-source-review-consolidator](#multi-source-review-consolidator) | 合并多份复习笔记为一份结构化文档 |
| [paper-finder](#paper-finder) | 关键词检索文献、下载 PDF 并生成 MD 备份 |
| [pdf-reader](#pdf-reader) | 读取并提取 PDF 中的文字 |
| [pptx](#pptx) | 创建、读取、编辑 PowerPoint 演示文稿 |
| [raft-report-updater](#raft-report-updater) | 通用实验报告更新工具 |
| [skill-vetter](#skill-vetter) | 安装技能前的安全审查 |
| [uv-python-runner](#uv-python-runner) | 在 uv 管理的 Python 环境执行脚本 |
| [zotero-paper-reader](#zotero-paper-reader) | 从 Zotero 读取和分析论文 |

## 文档排版与笔记

### course-review-generator

从课程 PPT 幻灯片（PDF 格式）生成结构化的复习笔记。扫描课程目录中的 PDF 文件，按章节分批提取文字，将关键概念整理成包含表格和公式的完整 Markdown 复习文档，并可选地转换为 PDF。适用场景：根据课件制作考试复习资料、整理 PPT PDF 的课程笔记、批量将讲义 PDF 转换为学习指南。

### makenote

笔记构建助手，围绕一份以「当前工作目录名.md」命名的 Markdown 笔记文件工作。通过 /makenote 口令或直接发送文字/文件，在对话中完成笔记的新增、修改、订正与补充；课件先转 pandoc 干净格式再摘录，课本 PDF 默认不全量读取。触发词：「/makenote」「做笔记」「记笔记」「整理笔记」。

### makepaper

读取指定文件夹内的 Markdown 资料（文献 md，可能只有摘要或含全文），按用户要求合成带 [n] 交叉引用的高质量中文论文，输出为可交给 makelatex 转 PDF 的 Markdown。用于依据若干 md 资料写论文/报告/综述。

### makelatex

把带交叉引用/角标（如正文中的 [1]）的 Markdown 文档转换成排版规范的中文 PDF（LaTeX/tectonic + ctex），正文引用渲染为角标并保留参考文献表。适用于需要 LaTeX 排版的中文课程作业、报告、笔记等含 [n] 引用的 Markdown 转 PDF；不含引用的普通 Markdown 转 PDF 请直接用 pandoc。

### md-latex-to-docx

将 Markdown、LaTeX 或 XeLaTeX 文档转换为符合中文论文规范的完整 Microsoft Word（.docx）文件。应用正确的字体（宋体、Times New Roman、Arial）、标题字号（三号/四号/小四）、1.5 倍行距、图表标题格式、三线表、OMML 公式和参考文献格式。适用场景：将 .md/.tex 转为 .docx、为投稿排版学术论文/学位论文、生成符合 SCI 期刊规范的 Word 文档、应用中文论文排版规范。

### multi-source-review-consolidator

将多份 AI 生成的复习笔记文件（txt/md）合并为一份结构化的 Markdown 复习文档。合并重复内容、去重词汇和语法知识点、按章节/课时统一排版，并可选择按类别（如语法/课文与词汇）拆分为多个文件。适用场景：合并多份 AI 生成的学习指南、把零散的复习笔记整合成一份文档、整理多个来源的课程复习资料、把合并后的复习拆分为语法和词汇部分。

## 文献与 PDF

### paper-finder

按关键词检索学术文献，返回经校验的标题、作者、期刊、年份、DOI 与摘要；人工筛选后可按分类下载 PDF，并生成 Markdown 内容备份（元数据+摘要+开放获取全文）。用于校园网环境下的论文查找、筛选与整理；不负责谷歌学术抓取。

### zotero-paper-reader

从 Zotero 文献库中读取和分析学术论文。当用户要求按标题、作者或主题读取、访问或分析其 Zotero 库中的论文时使用。自动搜索 Zotero、将 PDF 转为 Markdown、保存到 Notes/PaperInMarkdown，并提供分析。

### pdf-reader

读取并提取 PDF 文件中的文字。当用户要求读取、打开、提取或分析 PDF 文档时使用。支持中文和英文 PDF。自动将 PDF 页面转换为保留格式的可读文本。适用场景：阅读 PDF、提取 PDF 内容、将 PDF 转为文本、分析 PDF 文档。

## 科研与数据

### gpc-plot

高分子 GPC/SEC 色谱图绘制。解析 Agilent（Cirrus 软件）GPC 数据文件，生成 EPS+TIF 图谱。支持单文件、多曲线叠加组图、批量逐个出图三种模式。触发词：「GPC」「画GPC」「GPC图」「色谱图」「SEC」「分子量分布」「Cirrus」「194/195/196 等编号的txt」「dw_dlogM」「保留时间」。

### raft-report-updater

通用实验报告更新工具。自动读取项目目录下的 Excel 数据文件和已有 Markdown 报告，检测数据变更与矛盾，重新生成完整实验报告并按日期归档。适用场景包括但不限于：聚合物 RAFT/ATRP 可控聚合、有机合成条件筛选、材料性能测试矩阵、催化剂活性评价等任何以 Entry 编号组织的实验数据。触发词：「更新报告」「更新实验报告」「刷新报告」「加数据」「添加实验」「update report」。

## 演示文稿

### pptx

只要涉及 .pptx 文件——无论是作为输入、输出还是两者兼有——就使用此技能。包括：创建幻灯片组、路演文稿或演示文稿；读取、解析或提取任何 .pptx 文件中的文本（即使提取的内容会用于其他地方，如邮件或摘要）；编辑、修改或更新现有演示文稿；合并或拆分幻灯片文件；处理模板、版式、演讲者备注或批注。只要用户提到 "deck"、"slides"、"presentation"，或引用 .pptx 文件名，无论之后打算如何处理内容，都应触发。

## 开发与技能管理

### git-use

连接本地项目与 GitHub 仓库并上传（push）的完整流程，包括 HTTPS 令牌认证、克隆/初始化后推送、.gitignore 与敏感信息检查，以及本机常见故障（schannel 报错、代理、凭据管理器卡住、dubious ownership）。触发词：「git」「github」「上传」「push」「clone」「推送到 GitHub」。

### find-skills

帮助用户发现和安装 Agent 技能。当用户提出类似"我怎么做 X"、"找一个能做 X 的技能"、"有没有可以……的技能"等问题，或表达出扩展功能的需求时触发。当用户寻找的功能可能以可安装技能的形式存在时，应使用此技能。

### skill-vetter

面向 AI Agent 的安全优先技能审查工具。在从 ClawdHub、GitHub 或其他来源安装任何技能之前使用，检查危险标志、权限范围和可疑模式。

### uv-python-runner

在 uv 管理的 Python 环境中执行 Python 脚本。当默认 Python 由 uv 管理（出现 externally-managed-environment 报错）、pip install 失败，或需要处理中文路径和特殊字符文件名时使用。涵盖用于一次性脚本的 uv run --with 和用于环境管理的 uv pip。

# 🧰 han-skills

个人常用 Codex 技能库，长期维护、持续更新。

一套面向 [Codex](https://openai.com/codex) 场景的个人技能（Skills）集合，覆盖文档排版、文献管理、科研绘图与数据处理、演示文稿、开发与技能管理等方向，当前共 **15 个技能**。

---

## 🚀 快速开始

```powershell
# 1. 克隆仓库
git clone https://github.com/han90059005/han-skills.git

# 2. 按需把技能复制到本地技能目录
Copy-Item -Path "han-skills\pdf-reader" `
          -Destination "$env:USERPROFILE\.agents\skills\pdf-reader" `
          -Recurse -Force
```

> 本地技能目录通常是 `C:\Users\<你的用户名>\.agents\skills`。一次只装需要的即可，装上后新开一个对话就能用自然语言触发。

## 📦 技能总览

| 技能 | 分类 | 一句话说明 |
| --- | --- | --- |
| [course-review-generator](#course-review-generator) | 📝 文档 | 从 PPT 生成或合并复习笔记 |
| [makenote](#makenote) | 📝 文档 | 交互式维护一份 Markdown 笔记 |
| [makepaper](#makepaper) | 📝 文档 | 依据文献 md 合成带引用的中文论文 |
| [makelatex](#makelatex) | 📝 文档 | 含交叉引用的 Markdown 转中文 PDF |
| [pandoc-docx](#pandoc-docx) | 📝 文档 | Markdown/LaTeX 转中文论文规范 Word |
| [paper-finder](#paper-finder) | 📚 文献 | 检索文献、下载 PDF、生成 MD 备份 |
| [zotero-paper-reader](#zotero-paper-reader) | 📚 文献 | 从 Zotero 读取和分析论文 |
| [pdf-reader](#pdf-reader) | 📚 文献 | 提取 PDF 中的文字 |
| [gpc-plot](#gpc-plot) | 🔬 科研 | 绘制 GPC/SEC 色谱图 |
| [raft-report-updater](#raft-report-updater) | 🔬 科研 | 实验报告自动更新与归档 |
| [pptx](#pptx) | 🎬 演示 | 创建、读取、编辑 PowerPoint |
| [git-use](#git-use) | 🛠️ 开发 | 本地与 GitHub 互传 |
| [find-skills](#find-skills) | 🛠️ 开发 | 发现并安装技能 |
| [skill-vetter](#skill-vetter) | 🛠️ 开发 | 安装技能前的安全审查 |
| [uv-python-runner](#uv-python-runner) | 🛠️ 开发 | uv 环境下执行 Python 脚本 |

## 📚 技能详情

### 📝 文档排版与笔记

#### course-review-generator

从课程 PPT（PDF）生成结构化复习笔记，或把多份已有的复习笔记/学习指南合并去重为一份 Markdown。支持扫描版 PDF 的视觉回读，可输出 Markdown 并可选转 PDF。

- **触发**：整理 PPT 复习资料 / 合并复习笔记 / 生成复习清单
- **相关**：内容生成后的排版交给 [makelatex](#makelatex)（PDF）或 [pandoc-docx](#pandoc-docx)（Word）

#### makenote

围绕一份固定 Markdown 笔记文件，随对话增量维护（新增、修改、订正、补充），自动维护「记忆快照区」以便跨会话续写。

- **触发**：/makenote / 做笔记 / 记笔记
- **相关**：批量生成复习资料用 [course-review-generator](#course-review-generator)

#### makepaper

读取文献 Markdown，合成带 `[n]` 角标引用的高质量中文论文/综述，输出可直接交给 makelatex 的 Markdown。

- **触发**：依据 md 资料写论文 / 综述
- **相关**：排版用 [makelatex](#makelatex)（PDF）或 [pandoc-docx](#pandoc-docx)（Word）

#### makelatex

把含 `[n]` 交叉引用的 Markdown 转成中文 PDF（Tectonic + ctex），正文引用渲染为角标并保留参考文献表。

- **触发**：Markdown 转 PDF / 含引用的文档排版
- **依赖**：Tectonic（无需 TeX Live）

#### pandoc-docx

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

#### pdf-reader

提取 PDF 中的文字（中英文），尽量保留格式；文本版走 pdfplumber/pymupdf，扫描版需 OCR。

- **触发**：读 PDF / 提取 PDF 文字
- **依赖**：uv 管理依赖

### 🔬 科研与数据

#### gpc-plot

解析 Agilent（Cirrus 软件）GPC 数据文件，绘制 EPS+TIF 色谱图；支持单文件、多曲线叠加、批量出图。

- **触发**：GPC / 色谱图 / SEC / 分子量分布
- **依赖**：matplotlib + numpy

#### raft-report-updater

读取 Excel 数据与已有 Markdown 报告，检测数据变更与矛盾，重新生成完整报告并按日期归档，适合以 Entry 编号组织的实验数据。

- **触发**：更新实验报告 / 加数据 / 添加实验

### 🎬 演示文稿

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

## 🧱 环境依赖

| 依赖 | 用途 | 说明 |
| --- | --- | --- |
| Python + uv | pdf-reader、gpc-plot 等 | 系统自带 Python 3.9/3.12 或 uv 均可 |
| pandoc ≥ 3.0 | course-review-generator、pandoc-docx | 安装于 `C:\Program Files\Pandoc` |
| Tectonic | makelatex | 单文件即可，无需 TeX Live |
| TeX Live（可选） | pandoc 出 PDF（xelatex） | 深度使用 LaTeX 时建议安装完整版 |
| Zotero Desktop | zotero-paper-reader | 需开启本地 API |
| matplotlib + numpy | gpc-plot | 系统 Python 或 `uv run --with` |

## 🗂️ 目录结构

```text
han-skills/
├── course-review-generator/
├── find-skills/
├── git-use/
├── gpc-plot/
├── makelatex/
├── makenote/
├── makepaper/
├── pandoc-docx/
├── paper-finder/
├── pdf-reader/
├── pptx/
├── raft-report-updater/
├── skill-vetter/
├── uv-python-runner/
└── zotero-paper-reader/
```

## 🔄 维护约定

- **新增技能**：复制到本仓库根目录，并按分类同步更新「技能总览」和「技能详情」。
- **修改技能**：同步更新对应详情、触发词与描述。
- **隐私**：含个人信息的技能（如 `hanjinhong-profile`）默认只留在本地，不上传公开仓库。

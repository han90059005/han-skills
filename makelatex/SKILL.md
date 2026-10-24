---
name: makelatex
description: "把带交叉引用/角标（如正文中的 [1]）的 Markdown 文档转换成排版规范的中文 PDF（XeLaTeX + ctex），正文引用渲染为角标并链接到文末文献表，列表、表格、公式、代码块、图片按 Markdown 语义还原。适用于需要 LaTeX 排版的中文课程作业、实验报告、调研报告等含 [n] 引用的 Markdown 转 PDF；不含引用的普通 Markdown 转 PDF 请直接用 pandoc。"
metadata:
  short-description: 带交叉引用的 Markdown 转中文 LaTeX PDF
---

# makelatex

把一份带 `[n]` 交叉引用的 Markdown 文件转成中文 PDF：正文里的 `[1]`、`[1,2]`、`[1-3]` 自动变成上角标并链接到文末文献表，列表 / 表格 / 公式 / 代码块 / 图片按 Markdown 语义还原，最后用 XeLaTeX（TeX Live）+ ctex 编译。

优先运行脚本，不要手写 LaTeX 环境：

```bash
python scripts/md_to_latex_pdf.py 输入.md --output 输出目录
```

脚本在输出目录生成同名 `.tex` 与 `.pdf`；中间文件放 `build/`，成功后自动清理，源目录只留 `.tex`、`.pdf` 和图片 `assets/`。

## 常用参数

| 参数 | 作用 |
|---|---|
| `--output` / `-o` | 输出目录，默认与 md 同目录 |
| `--name` | 输出文件名（默认取 md 主名） |
| `--title` / `--author` / `--date` | 覆盖自动识别的标题、作者行、日期行 |
| `--toc` | 生成带点线引导的目录（≥3 个标题时值得开） |
| `--bib-sort` | 按正文首次引用顺序重排文献编号（GB/T 7714 顺序编码制） |
| `--fontset auto\|windows\|fandol\|mac` | 中文字体集，默认 auto |
| `--xelatex` | 指定 xelatex.exe 路径，默认自动探测 |
| `--star-sections` | 标题全部不编号（默认自动编号并写入 PDF 书签） |
| `--no-compile` | 只生成 `.tex` |
| `--keep-log` / `--verbose` | 成功后保留 `build/` 日志 / 打印完整编译输出 |

## 输入约定

- 第一个 `# 标题` 作为 PDF 标题；标题之后含「姓名 / 学号 / 作者」的行作为作者行，含「日期 / Date」的行作为日期行。
- 正文空行分段；`## 参考文献`（或 `References`）之后的部分作为文献表，条目以 `[n]` 开头。
- 引用写成 `[1]`、`[1,2]`、`[1-3]`。区间会展开成对应条目（`[1-3]` 渲染为 `[1, 2, 3]` 并逐条链接）。
- `$...$`、`$$...$$` 原样透传（已加载 amsmath/amssymb）；数学片段里的方括号不会被当成引用。
- 支持 `**粗体**`、`*斜体*`、`` `行内代码` ``、`[文字](https://…)` 链接、`- / 1.` 列表、`|` 表格（含表头分隔行）、``` 围栏代码块、`> 引用`、`---` 分隔线。
- 图片既可写成独立一行的 `![说明](images/fig1.png)`（自动生成 figure + 图题），也可在 `.tex` 里手写 `\includegraphics`（graphicx 已加载）。

## 标题编号规则

- 文档里所有标题都没有自带编号 → 自动编号（`\section{…}`），并进目录与 PDF 书签。
- 只要有一处标题自带编号（如 `## 1.2 方法`、`## 二、结果`）→ 认为编号由作者自己维护，全部标题改为不编号，避免出现「0.1 子标题」这类半自动错号。
- `--star-sections` 强制不编号。

## 参考文献

脚本把 `[n] 条目` 编译成 `\bibitem`，正文 `[1]` 变成 `\textsuperscript{\cite{ref1}}`，因此：

- 编号由 LaTeX 维护，中间插入一条文献不会让正文角标错位；
- 生成时做一致性检查并在 stdout 打印「提示」：引用了文献表里不存在的编号、文献表条目未被引用、文献表未按首次引用排序（建议加 `--bib-sort`）；
- 文献表标题为中文章「参考文献」，条目悬挂缩进，并作为书签项写入目录。

已知取舍：不做 GB/T 7714 的字段级重排（著者、题名、`[J]`/`[M]` 等标点由作者写在 md 里，原样保留）。要严格国标排版请用学位论文模板（如 nwputhesis），本技能只负责「md → 能交作业的 PDF」。

按国标手写条目即可，脚本不解析字段：

```
[1] Moad G, Rizzardo E, Thang S H. Living radical polymerization by the RAFT process[J]. Australian Journal of Chemistry, 2005, 58(6): 379-410.
```

## 编译与排错

- 自动多遍编译（默认 2 遍；有文献或目录时最多 3 遍，按 `.aux` 是否稳定 + 日志里的 `Rerun` 决定），完成后把 PDF 从 `build/` 拷回输出目录。
- 编译失败时**保留** `build/<name>.log`，并打印第一条错误（`文件:行号` 形式）与日志路径；不要盲目重跑，先读那条错误。
- 成功但仍有 warning 时提示条数，`--keep-log` 可保住日志细看。
- 找不到 xelatex 时显式指定：`--xelatex D:\AI-tools\latex\texlive\2026\bin\windows\xelatex.exe`。

## 环境

1. **需要 XeLaTeX**：默认按 PATH → `XELATEX` 环境变量 → `D:\AI-tools\latex\texlive\*\bin\windows\xelatex.exe` 等常见路径探测。
2. **中文字体**：`fontset=auto` 时先看 `%WINDIR%\Fonts\simsun.ttc`，有就用 `windows`，否则退回 TeX Live 自带的 `fandol`；`mac` 供 macOS 用。字体缺失是这台机器上最常见的编译失败原因。
3. **宏包**：ctex、geometry、amsmath、graphicx、setspace、fancyhdr、hyperref、tocloft 都在完整 TeX Live 内，不需要联网。
4. **图片路径**：按 md 所在目录解析；输出目录与 md 目录不同时，图片自动复制到输出目录的 `assets/` 再引用（规避中文路径与相对路径问题）。图片缺失时画占位框并提示，不中断编译。

## 校验产物

```bash
pdftoppm -png -r 110 输出.pdf page      # 看版式：标题块、目录、表格框线、页码
pdftotext -layout 输出.pdf -            # 抽文本核对角标与文献表
```

- 中文在 `pdftotext` 里可能显示乱码，这是抽取层编码问题，不代表 PDF 渲染错误；重点看 `[n]` 角标数量与文献条数是否一致。
- 页码在页脚居中；标题、作者写进 PDF 元数据（`pdftitle` / `pdfauthor`）。

## 插入签名 / 照片

graphicx 已加载，直接在生成的 `.tex` 里加 `\includegraphics` 即可：

- **格式**：PNG、JPG、PDF 均可；PNG 对签名/线稿/透明底更好，文件名建议用 ASCII。
- **只设宽度**：`width=2.23cm`，高度按原图比例缩放，不会拉伸。
- **确定尺寸**：来源是 Word 时，解包 `.docx` 看 `word/document.xml` 里 `<wp:extent cx="..." cy="..."/>`，按 `1cm = 360000 EMU` 换算。
- **位置**：右对齐签名用 `\begin{flushright}…\end{flushright}` 包住，图片底部即对齐文字基线。

若目标机器没有 TeX Live，可用 TinyTeX 的 xelatex，但需自行补装 ctex 等宏包并配置字体。

## 不支持的写法

嵌套列表会拍平为同级；合并单元格的表格、跨行表格、脚注、参考文献自动抓取都不处理——遇到就手工改 `.tex`。

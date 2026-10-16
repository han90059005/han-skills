---
name: makelatex
description: "把带交叉引用/角标（如正文中的 [1]）的 Markdown 文档转换成排版规范的中文 PDF（LaTeX/tectonic + ctex），正文引用渲染为角标并保留参考文献表。适用于需要 LaTeX 排版的中文课程作业、报告、笔记等含 [n] 引用的 Markdown 转 PDF；不含引用的普通 Markdown 转 PDF 请直接用 pandoc。"
metadata:
  short-description: 带交叉引用的 Markdown 转中文 LaTeX PDF
---

# makelatex

把一份带 `[n]` 交叉引用的 Markdown 文件转成中文 PDF：正文里的 `[1]`、`[1,2]`、`[1-3]` 会变成上角标，文末的「参考文献」表保持 `[n]` 编号并做斜体/粗体处理，最后用 tectonic（XeTeX + ctex）编译。

## 使用方式

优先运行脚本，避免重复手写 LaTeX 和环境配置：

```bash
python scripts/md_to_latex_pdf.py 输入.md \
  --output 输出目录 \
  --tectonic D:\tectonic-0.17.0-x86_64-pc-windows-msvc\tectonic.exe
```

脚本会在输出目录生成同名的 `.tex` 和 `.pdf`。常用参数：

- `--title / --author / --date`：覆盖自动识别的标题、作者、日期
- `--name`：指定输出文件名（默认用输入文件的主名）
- `--tectonic`：tectonic.exe 路径（不指定时自动探测）
- `--cache-dir`：宏包缓存目录（默认 `<tectonic.exe 所在目录>\cache`）
- `--no-compile`：只生成 `.tex`，不编译

## 输入约定

- 第一个 `# 标题` 作为 PDF 标题
- 标题后含「姓名 / 学号 / 作者」的行作为作者行，含「日期 / Date」的行作为日期行
- 正文空行分段；`## 参考文献`（或 `References`）之后的部分作为参考文献表
- 正文引用写成 `[1]`、`[1,2]`、`[1-3]`；参考文献条目以 `[n]` 开头
- 正文可用 `$...$`（行内）与 `$$...$$`（行间）书写数学公式，脚本原样透传、不转义（基础数学用 LaTeX 内核即可，无需 amsmath）

## 关键环境处理（本机已踩过的坑）

1. **缓存目录**：脚本默认把宏包缓存写到 `tectonic.exe` 同目录的 `cache`，避开受限沙箱下默认 `%LOCALAPPDATA%` 缓存的「拒绝访问」。若该目录本身只读（如 tectonic 装在 D: 盘、沙箱只读挂载），tectonic 更新缓存会 panic（os error 5 拒绝访问）；脚本已自动检测可写性，不可写时回退到系统临时目录并尽量从原缓存复制已有宏包，避免重复联网下载。
2. **代理导致下载失败**：tectonic 首次运行要从 `relay.fullyjustified.net` 下载宏包；走本机 Clash（`127.0.0.1:7897`）会报 `tls handshake eof`。脚本会自动清空 `HTTP_PROXY / HTTPS_PROXY` 并设 `NO_PROXY=*` 直连。
3. **中文字体**：模板用 `ctexart` 的 `fontset=windows`，依赖 Windows 自带的 SimSun/SimHei/KaiTi。
4. **验证**：用 `pdftoppm -png` 渲染预览；用 pypdf 抽取文本检查角标时，中文可能显示为乱码，这是抽取层的编码问题，不代表 PDF 渲染错误——重点检查 `[n]` 角标数量和英文参考文献即可。
5. **数学字体也需联网**：首次编译含数学公式的内容时，tectonic 还需下载 Computer Modern Type1 字体（cmmi10.pfb、cmr10.pfb、cmsy10.pfb 等），同样要走网络；受限沙箱下需先请求网络权限。基础数学（`\frac`、`\langle\rangle`、希腊字母、上下标）用 LaTeX 内核即可，不必引入 amsmath/amssymb。

## 插入图片（签名、照片等）

生成的 `.tex` 若需插图（例如家长签字、照片），手动加两处即可：

1. 宏包：`\usepackage{graphicx}`。`graphicx` 依赖 `graphics`、`xetex.def` 等，**首次需要联网下载**——默认/已缓存目录里可能没有（本机踩过坑：缓存里有 geometry/setspace 却没有 graphicx），受限沙箱下要先请求网络权限。
2. 插入：`\includegraphics[width=2.23cm]{signature.png}`，图片放到 `.tex` 同目录。

要点：

- **格式**：PNG、JPG、PDF 均可；PNG 无损，对签名/线稿/透明底更优，JPG 适合照片。图片文件名建议用 ASCII（不带中文），避免 XeLaTeX 中文路径兼容问题。
- **只设宽度**：写 `width=...` 一项即可，高度按原图比例自动缩放，不会拉伸变形。
- **确定正确尺寸**：来源是 Word 文档时，解包 `.docx` 看 `word/document.xml` 里图片的 `<wp:extent cx="..." cy="..."/>`，EMU 换算 `1cm = 360000 EMU`，即可还原原文档的显示宽高（例如 `cx="802800" cy="360000"` → 2.23cm × 1.00cm）。
- **位置**：右对齐签名用 `\begin{flushright}...\end{flushright}` 包裹，`\includegraphics` 紧跟「签字：」之后，图片底部即对齐文字基线，看起来像手写签名。

如果目标机器没有 tectonic，可改用 TinyTeX 的 xelatex，但需同步调整编译命令和字体配置。

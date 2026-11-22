# 质量门槛与实战教训

本文件收的是「按 SKILL.md 走完之后还要检查什么」，以及踩过的坑。都是 2026-11-15
给《柔性电子材料基础》课件讲义配图时留下的现场记录。

## 一、取图前先判断：这张图值不值得裁

渲染幻灯片 300 dpi **不会**增加信息。判断方法：

```
有效 dpi ≈ 该图在源文件里的像素宽 ÷ 它在 PDF 里的物理宽度(英寸)
```

- 源图 ≥ 800 px 且成品宽 ≤ 6 cm → 直接裁；
- 源图 100–200 px（课上常见的小结构式、小示意图）→ **重画**，放大只会得到马赛克；
- 介于两者之间 → 先裁一张试试，在 150 dpi 下看不清就重画。

典型例子：课件里 P3HT 结构只有约 120×110 px，放进 2×2 拼版当一格会糊成墨团，
最后用 `draw_polymer.py` 重画了重复单元。

## 二、裁切的三条自检

1. **原子/单位标签不能被切**：`C₆H₁₃`、`CN`、坐标轴单位最容易被切掉半个字；
2. **邻图残边必须去掉**：并排画的结构常常只差 20 px 就带进隔壁分子的弧线；
3. **图表轴线不能残留**：从柱状图/光谱图上方裁图时，底边容易带进一条黑轴。
4. **课件标题栏和页码要剪掉**：多数课件页顶部有蓝色标题条、右下角有页码。走
   `grab2.py` 的「内容区域」兜底路径时这两样必然带进来——裁完先看顶部 3% 和右下角。

裁完一定 `read_image` 看一眼，不要凭坐标想象结果。

## 三、拼版

- 先各自去白边，再按单元等比缩放——不要拉伸；
- 灰底图必须先去底（`crop.py --whiten 30`）或换白底源图，否则四格颜色不一致；
- 2×2 适合 4 张；1×2 或 1×3 适合宽图（能谱、能级图）；
- 两个分子尺寸差很多时，宁可按「高度对齐」而不是「面积对齐」，视觉上更稳。

## 四、插进 Markdown

```markdown
![](<课件图/3-4 典型给体与受体结构.png>){width=88%}

**图 3-4** ……（P39–46）
```

- **图注后必须空一行**，否则 pandoc 把紧跟着的 `-` 列表并进图注段落；
- 图注写全：图号、内容、每格对应的课件页码；自绘的写「自绘」；
- 图片路径含空格和中文时用 `<...>` 包住；
- 图宽 80%–90% 比较稳，100% 会顶到版心边缘。

### 图注别依赖 pandoc 的隐式 figure

图多的时候（20 张以上）用 `![图注](path){width=..}` 的隐式 figure 不可靠：实测 pandoc
有的版本根本不发 `\caption`，图注退化成一个普通段落，**页底被拆开**。稳妥做法是直接写
figure 环境，编号交给 LaTeX：

````markdown
```{=latex}
\begin{figure}[H]
\centering
\includegraphics[width=0.9\linewidth]{课件图/图文版/f03 导电带宽.png}
\caption{绝缘体/半导体/共轭聚合物/导体四类能带（课件 2.3 P16）}
\end{figure}
```
````

配套三件事：header 里加 `\usepackage{graphicx}`（图片进了 raw block，pandoc 不会再自动加载）、
`\usepackage{float}` + `\def\fps@figure{H}`（防漂移）、`\renewcommand{\figurename}{图}` +
`caption` 包 `labelsep=quad`（去掉“Figure 1:”）。

注意顺序：**先跑 `subfix.py`，再把图注并进图**。反过来的话，图注里的 `ΔE_ST` 会漏转，
报 `Missing $ inserted`。


## 五、重建 PDF

顺序固定：`subfix.py` → 拼 header → `pandoc`。

```bash
python scripts/subfix.py 讲义.md build/jc_sub.md
cp reference/latex-header.tex build/header.tex
cd <课程目录> && pandoc build/jc_sub.md -o build/final.pdf --pdf-engine=xelatex \
  -H build/header.tex -V mainfont="Times New Roman" -V CJKmainfont="SimSun" \
  -V geometry:a4paper -V geometry:margin=2.5cm --toc --toc-depth=2 -V toc-title=目录
```

- 页数变动是正常的：加图会增页，重排可能又压回去。**以内容完整为准，不追求页数不变**；
- 改前 `cp 原.pdf 原.pdf.bak-YYYYMMDD`，md 同样留备份；
- 校验：`pdfinfo` 看页数、`pdftoppm -r 150` 看目标页、`pdftotext` 搜图注文字。

## 六、已知故障

| 症状 | 真实原因 | 处理 |
|---|---|---|
| `BadZipFile: Bad CRC-32` | 课件里的 mp4/png 损坏，python-pptx 读不了 | 复制 zip、替换损坏条目为占位符再解 |
| COM 报 "could not open" | `WithWindow=$false` | 改 `$true` |
| COM 报 "路径不存在" | .ps1 无 BOM，中文路径按 GBK 解析 | 写 BOM |
| `Missing $ inserted` | 正文里 `∬` 等符号在数学环境外 | 预处理成 `$\iint$` |
| `Unused global option(s)` | `10.5pt` 不是合法 classoption | 用 10/11/12pt，或调 geometry |
| 缺字形警告 `∝ ≤ ⭐` | xeCJK 未映射 | header 里 `\newunicodechar` 补映射 |
| 图注变成列表 | 图注后缺空行 | 补空行 |
| 写文件 PermissionError | 解释器被限制写该目录 | 输出到工作目录再拷 |

## 七、来源纪律

- 图注里「课件原图」和「自绘」必须分开写清楚；
- 课件里没有的结构（例如只在正文提过的 Y6），**要么明说没有，要么等拿到可靠结构再画**，
  不要用相近分子顶替还不标注；
- 用课件原图时标注页码，方便核对。

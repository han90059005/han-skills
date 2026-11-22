---
name: slide-figure
description: '把课件/文献里的图变成笔记 PDF 里的图：PPTX 渲染取图、裁切去底、拼版、按需重画（化学结构式、聚合物重复单元），再插进 Markdown 并重建 PDF。当用户说"给这份讲义插几张图""把课件里的图抠出来""PPT 里的图提取到笔记""画个结构式""拼个对比图"，或已有的课件笔记缺图/图太糊时使用。读图里的文字与公式走 mineru，写正文走 makenote / course-review-generator，最终排版走 makelatex。'
argument-hint: '[课件路径或笔记路径]'
---

# Slide Figure — 课件配图流水线

## 这个技能解决什么

做课程讲义/复习资料时，正文好写、**图难办**，卡点通常是三个：

1. 课件里的图是嵌在 PPT 里的位图（常只有 1000 px），直接抽出来糊得没法看；
2. 有些图（结构式、示意图）课件里根本没有，或者小到不可用，只能重画；
3. 图放进 Markdown 后，PDF 构建那套参数（角标、页眉、A4、目录）每次都要试一遍。

本技能把这条链固定成五步：**渲染 → 裁切 → 拼版 → 重画（按需）→ 插入并重建**，每一步都有脚本和判据。

## 三条红灯

1. **分辨率不够就重画，不许放大充数。** 渲染 300 dpi 只是把 1000 px 的位图插值，不会变清晰。判据：目标物理宽度下的有效 dpi < 150 时，必须 `draw_polymer.py` / `draw_mol.py` 重画，或换源图。
2. **结构式不许凭记忆写。** SMILES 一律走 `mol_lookup.py` 查库；查不到就明确告知用户并改用课件原图，**不要猜**。
3. **图注必须带课件页码，手绘图必须标明来源。** 课件原图标 `（P39）`，自绘图注写「自绘」；不能让读者以为手绘的是课件原图。

## 环境常量

| 用途 | 命令/路径 |
|---|---|
| 渲染 PDF 页 | `pdftoppm`（poppler，已在 PATH） |
| PPTX → PDF | PowerPoint COM，`Presentations.Open(src, $true, $false, $true)`；`WithWindow=false` 会报 "could not open" |
| 谁跑 COM | **主机 PowerShell**（`pwsh` 工具）。在 bash 沙箱里跑会报 SaveAs 找不到路径，或"成功"但什么也没写出来 |
| PowerShell 脚本 | 含中文路径必须写 **UTF-8 BOM**，否则路径乱码 |
| RDKit | 独立 venv：`D:\AI-tools\rdkit-venv\Scripts\python.exe` |
| Python（matplotlib 出图） | `C:\Users\admin\AppData\Local\Programs\Python\Python312\python.exe`（3.12 + matplotlib 3.10.9；PATH 上的 `python` 是 WindowsApps 占位符，不可用） |
| 默认 PyPI | 不通；装包用 `-i https://pypi.tuna.tsinghua.edu.cn/simple`（阿里云镜像同样可用） |
| 输出位置 | 写到工作目录，不要写 `%TEMP%`（某些解释器会被拒写） |

## 流程 A：从课件取图

```bash
# 1) 找到图在哪一页（用 pptx 的 slide 号 = PDF 页码）
#    COM 导出这一步走主机 PowerShell；已有 PDF 时脚本会跳过导出
python scripts/slides2png.py "课件/3.2 有机光伏材料.pptx" --outdir fig --pages 39,41,44,46 --dpi 300

# 2) 目视定框，裁切（先宽松，再收紧）
python scripts/crop.py fig/page41.png fig/pcbm.png --box 1025,945,1548,1875 --pad 14

# 3) 多张拼成一张（统一白底、自动缩放对齐）
python scripts/compose.py fig/fig-3-4.png fig/a.png fig/b.png fig/c.png fig/d.png --cols 2 --cell 1080x760
```

**定框技巧**：先把整页按 70~80 dpi 看一眼估坐标，再按 300 dpi 的实际尺寸裁（坐标 × 缩放比）。裁完必看一遍，重点查三样：原子/单位标签有没有被切、邻图的残边有没有带进来、拼接处有没有非白背景。

## 流程 B：重画

- **聚合物重复单元**（P3HT/P3OT 这类）：

```bash
python scripts/draw_polymer.py fig/p3ht.png --label P3HT --side 6
```

- **小分子结构式**（有 SMILES 时）：

```bash
python scripts/mol_lookup.py ITIC          # 先查，拿到 SMILES 再画；网络不通会明确报错
D:/AI-tools/rdkit-venv/Scripts/python.exe scripts/draw_mol.py "$SMILES" fig/itic.png --label ITIC --size 1600x900
```

> RDKit 把三个噻吩环画成楼梯状，读起来很糟——聚合物一律用 `draw_polymer.py`，不要硬用 `draw_mol.py`。

### 示意图（能级图、轨道图、能带图）—— 直接 matplotlib 手写

结构式和重复单元走上面的脚本；轨道、能级、带隙这类示意图没有现成库，直接写 matplotlib。

- **一个脚本画全套**：`level()`（能级线）、`electrons()`（↑↓ 自旋箭头）、`lobe()`（参数化多边形画 p/sp 轨道瓣，`squash` 做透视压扁）、`arrow()`。脚本存进课程目录，图可一键重出。
- **字体**：`rcParams["font.sans-serif"] = ["SimHei"]`、`mathtext.fontset = "stix"`。**SimHei 没有 U+2212 减号**，`(8−4)` 会渲染成方块，减号写 `$(8-4)$`；小字号下 SimHei 的 `O` 与 `0` 难分，原子符号写 `$O$`。
- **尺寸**：`figsize` 宽 10–13 in、`dpi=220`、`bbox_inches="tight"`；插进 md 时 `{width=14~15cm}`。
- **必须看图迭代**：先存 PNG，用 `read_image` 逐张检查再调坐标，不要写完就交。三类高频撞车：① 面板标题/副标题与「节面」之类标注重叠；② 底部说明文字溢出到隔壁面板；③ 旋转的能量轴标签压住带隙箭头。
- **惯用坐标**：分子平面用椭圆透视盘；三个 sp² 瓣互成 120°（`squash≈0.4`），未杂化 2p_z 竖直；π 分子轨道侧视时碳骨架画成一条水平线，轨道瓣高度正比于分子轨道系数，红/蓝区分相位，节面画灰虚线。
- **内容先对课件**：能级顺序、电子排布、HOMO/LUMO 节面数这类事实，以课件原文为准（先 `pdftotext` 抽一遍），不要凭印象写。

## 流程 C：插进 Markdown 并重建 PDF

插入块（**图后必须空一行**，否则 pandoc 会把后续 `-` 列表并进图注）：

```markdown
![](<课件图/3-4 典型给体与受体结构.png>){width=88%}

**图 3-4** 典型给体与受体分子结构（课件原图）：左上 P3HT 重复单元（P39）；右上 PC₆₁BM（P41）……
```

重建（三步，顺序不能换）：

```bash
python scripts/subfix.py 讲义.md build/jc_sub.md                     # 角标 X_ab / 10⁻⁸ → LaTeX
cp reference/latex-header.tex build/header.tex                      # 页眉：章节名 + 页码
cd <课程目录> && pandoc build/jc_sub.md -o build/final.pdf --pdf-engine=xelatex \
  -H build/header.tex -V mainfont="Times New Roman" -V CJKmainfont="SimSun" \
  -V geometry:a4paper -V geometry:margin=2.5cm \
  --toc --toc-depth=2 -V toc-title=目录
```

改 PDF 前先 `cp 原.pdf 原.pdf.bak-YYYYMMDD`；md 同理。

## 质量门槛

| 项 | 判据 |
|---|---|
| 分辨率 | 最终 PDF 中 ≥ 150 dpi；结构式类建议 ≥ 300 dpi |
| 背景 | 纯白；灰底图用 `crop.py --whiten` 或换源 |
| 裁切 | 无切字、无邻图残边、无图表轴残段 |
| 图注 | 有名有页码；自绘注明「自绘」 |
| 版式 | 图宽 ≤ 90% 文本宽；图后空行；页码与正文对得上 |

## 常见故障

| 症状 | 原因 / 处理 |
|---|---|
| `PermissionError` 写不进目标目录 | 换工作目录输出；不要写 `%TEMP%` |
| COM 导出报 "路径不存在" | .ps1 缺 BOM，中文路径被按 GBK 读 |
| pandoc 报 `Missing $ inserted` | 正文有 `∬` 之类未转义的数学符号，先转 `$\iint$` |
| 图注吞掉后面的列表 | 图注后缺空行 |
| RDKit 画出来歪七扭八 | 换成 `draw_polymer.py` 的重复单元画法 |
| PubChem 超时 | 没代理；改用课件原图，别手写 SMILES |
| COM 报"找不到路径"/"成功但没文件" | 在 bash 沙箱里跑了；改从主机 PowerShell 执行 |
| RDKit 脚本写文件 PermissionError | 输出路径在 `%TEMP%`；改写进工作目录（I 盘/当前项目） |

细节与实战教训见 `reference/quality.md`。

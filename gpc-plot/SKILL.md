---
name: gpc-plot
description: 高分子 GPC/SEC 色谱图绘制。解析 Agilent（Cirrus 软件）GPC 数据文件，生成 EPS+TIF 图谱。支持单文件、多曲线叠加组图、批量逐个出图三种模式。触发词：「GPC」「画GPC」「GPC图」「色谱图」「SEC」「分子量分布」「Cirrus」「194/195/196 等编号的txt」「dw_dlogM」「保留时间」。
---

> ⚠ **维护提醒**：本 skill 有两份副本，修改时须同步更新：
> - `I:\all skill\gpc-plot\` ← 原始存档
> - `c:\Users\admin\.agents\skills\gpc-plot\` ← VS Code 生效副本

# GPC 色谱图绘制

## 核心脚本

`scripts/plot_gpc.py` — 单文件即可完成解析+绘图+多格式输出。

```
python scripts/plot_gpc.py <file.txt> [file2.txt ...] [-m overlay|separate] [-o DIR] [-x log|linear] [--xmin XMIN] [--xmax XMAX] [--no-legend]
```

### 参数

| 参数 | 说明 |
|------|------|
| `files` | 一个或多个 `.txt` 文件（必填） |
| `-m overlay` | 多曲线叠加到一张图（默认） |
| `-m separate` | 每个文件单独出图 |
| `-o DIR` | 输出目录（默认：第一个文件所在目录） |
| `-x log` | x 轴对数刻度 |
| `-x linear` | x 轴线性刻度（默认） |
| `--xmin X` | x 轴下限（不传则自动计算） |
| `--xmax X` | x 轴上限（不传则自动计算） |
| `--no-legend` | 隐藏左上角图例（保留右上角 Mn/PDI 标注表） |
| `--legend-loc LEGEND_LOC` | 图例位置（默认 `upper left`） |
| `--legend-fontsize N` | 图例字号（默认 8） |
| `--legend-frameon` | 显示图例边框 |
| `--legend-alpha N` | 图例边框透明度（默认 0.85） |
| `--border-lw N` | 边框线宽（默认 0.8） |
| `--border-color COLOR` | 边框颜色（默认 `#333333`） |
| `--line-width N` | 曲线线宽（默认 1.2） |
| `--line-colors C1,C2,...` | 按顺序指定每条曲线颜色 |
| `--line-color COLOR` | 所有曲线统一颜色 |
| `--font-family NAME` | 字体族（默认 `Arial`） |
| `--font-size N` | 基础字体大小（默认 12） |
| `--transparent-background` | 输出透明背景 |
| `--table-x X` | 右上角表格 X 轴位置（轴坐标，默认 0.65） |
| `--table-y Y` | 右上角表格 Y 轴位置（轴坐标，默认 0.96） |
| `--table-fontsize N` | 右上角表格字体大小（默认 8.5） |
| `--table-row-spacing N` | 右上角表格行间距（默认 0.06） |
| `--table-linewidth N` | 右上角表格线宽（默认 1.0） |
| `--no-table-lines` | 移除右上角表格所有横线（仅保留文字和色条） |
| `--no-save-source` | 不复制原始 `.txt` 数据文件到输出文件夹（默认会复制） |
| `--extend-tail` | 将曲线两端平滑延伸至 `--xmin` / `--xmax`。头部用三次 Hermite 插值强制 y(xmin)=0；尾部用指数衰减锚定末点，保证单调递减。延伸数据自动双向写入 `sources/`。默认关闭。 |
| `--readme TEXT` | 在 PNG 同目录保存 `readme.md`，内容为 TEXT（支持中英文双语说明） |

### 图例标签命名规则

**左上角图例标签 = 文件主名（不含扩展名）**。脚本不会使用 Cirrus 文件内部的 `Sample Name`（通常又长又丑，如 `001-P1-A1-F.D F RID1 A, Refractive Index Signal`），而是直接用 `.txt` 文件名作为标签。

> ⚠ **因此画组图前，务必把文件重命名为有意义的简短名字**（如 `NaF.txt`、`10min.txt`、`0.8eq.txt`），不要直接用原始编号文件名。推荐做法：复制到临时目录，改名后运行，画完删除临时目录。

### 输出结构

每个数据集生成一个子文件夹 + 一个 PNG 预览：

```
输出目录/
├── gpc_overlay/          ← 叠加模式固定名
│   ├── gpc_overlay.eps   ← 矢量图（300dpi，嵌入字体）
│   ├── gpc_overlay.tif   ← 位图（300dpi，论文投稿）
│   └── sources/          ← 默认自动生成
│       ├── NaF.txt
│       └── NaCl.txt
├── gpc_overlay.png       ← 快速预览（150dpi）
└── readme.md             ← --readme 时生成（中英文图注说明）
```

> ⚠ **多图输出防覆盖**：叠加模式输出名固定为 `gpc_overlay`。同时画多张组图时，必须使用不同的 `-o` 输出目录（如 `-o Fig1_卤素效应`、`-o Fig2_动力学`），否则后一张会覆盖前一张。

> ℹ **双向延伸**：`--extend-tail` 支持头部（向 xmin）和尾部（向 xmax）双向延伸。头部用三次 Hermite 插值强制 y(xmin)=0，尾部用指数衰减保证单调递减。延伸数据自动写入 `sources/` 中的转存 `.txt` 文件。默认关闭。

## 工作流程

### 1. 接收文件后，先确认

- **单文件还是多文件？**
- **多文件时，叠加还是分图？**
- **X 轴范围是否需要指定？** 默认自动计算（数据范围 ±3%），默认线性刻度。用户可以提供 `--xmin` / `--xmax`。
- **曲线两端是否需要外拓至 xmin/xmax？** 当数据在边界前截断导致留白时，可用 `--extend-tail`（需配合 `--xmin` / `--xmax`）。头部强制 y(xmin)=0，尾部保证单调递减。延伸数据双向写入转存源文件。- **边框、线条、字体、背景是否需要定制？** 支持 `--border-lw`、`--border-color`、`--line-width`、`--line-colors`、`--font-family`、`--font-size`、`--transparent-background`。
- **右上角表格位置与间距是否需要调整？** 支持 `--table-x`、`--table-y`、`--table-fontsize`、`--table-row-spacing`、`--table-linewidth`。- **输出到哪个目录？** 多张组图必须分别指定不同 `-o` 目录，防止互相覆盖。

### 2. 文件命名（关键步骤）

**图例标签 = 文件名（不含扩展名）**。画组图前必须给文件起有意义的名字：

| 文件原名 | 改名后 | 图例显示 |
|----------|--------|----------|
| `F.txt` | `NaF.txt` | NaF |
| `1.txt` | `10min.txt` | 10min |
| `0.8.txt` | `0.8eq.txt` | 0.8eq |

推荐做法：
```powershell
# 复制到临时目录并改名
$tmp = "path/to/_tmp"; New-Item -ItemType Directory -Force $tmp | Out-Null
Copy-Item "原始数据/--68--/F.txt" "$tmp/NaF.txt"
# ... 运行脚本 ...
Remove-Item -Recurse -Force $tmp  # 画完清理
```

### 3. 运行前检测格式

脚本内置 `detect_format()`，读取全文检测：
- `cirrus_agilent` (95%)：`Slice_Table` + `Cirrus`
- `generic_slice_table` (70%)：有 `Slice_Table` 无 Cirrus 标识
- `agilent_chemstation` (50%)：`Sample Chromatogram` / `GPC Results`
- `unknown`：无法识别

检测结果打印在控制台。对于 `unknown` 格式，**先读取文件头部确认结构**，不要跳过。

### 4. Python 环境

脚本依赖 `matplotlib` + `numpy`。优先使用系统已装好这些包的 Python（如 `C:\Users\<user>\AppData\Local\Programs\Python\Python312\python.exe`）。

```powershell
# 验证 matplotlib 可用
C:\Users\admin\AppData\Local\Programs\Python\Python312\python.exe -c "import matplotlib; print(matplotlib.__version__)"
```

若使用 uv 托管的 Python（`externally-managed-environment`），需走 `uv run --with matplotlib` 或 `uv pip install matplotlib`。

### 5. 运行

```powershell
$env:PYTHONIOENCODING='utf-8'; python <skill_dir>/scripts/plot_gpc.py ... 2>&1
```

**必须设置 `PYTHONIOENCODING=utf-8`**，否则 Windows 控制台中文路径乱码。

### 6. 验证

- 每个文件打印 `格式名 (置信度%)`
- 输出路径和文件名
- 无 error 即完成

## 图表样式

### 默认样式

- **四周黑框**：`#333333`，线宽 0.8（可通过 `--border-lw` / `--border-color` 调整）
- **曲线线宽**：1.2（可通过 `--line-width` 调整）
- **字体**：Arial（可通过 `--font-family` 调整）
- **无标题**：不显示样品名
- **无 y 轴**：刻度、标签、标题全部隐藏
- **无网格**
- **无峰值虚线**
- **无面积填充**：仅曲线描边
- **y 范围固定**：-0.05 ~ 1.1
- **x 轴**：线性（默认），整数刻度，步长 1，无科学计数法
- **图例标注（左上角）**：线条 + 文件名标签
- **数据标注（右上角）**：
  - 左侧：水平彩色条带
  - 右侧两列：`Mn` | `Đ`
  - Mn 四舍五入到百位，整数显示（如 16330 → 16300）
  - Đ 保留两位小数
  - 默认三线表（顶线/底线粗 1.5×，中栏线细 0.7×），可通过 `--no-table-lines` 去除横线
  - Mn ↔ Đ 列间距适中，行间距可通过 `--table-row-spacing` 调整
  - 表头到首行间距 = 行间距 × 0.4（自适应） |

### 论文推荐参数

```powershell
python plot_gpc.py ... --border-lw 1.8 --line-width 1.8 --font-size 14 \
    --legend-fontsize 14 --table-fontsize 12 --table-row-spacing 0.03 \
    --no-table-lines --transparent-background
```

| 参数 | 推荐值 | 说明 |
|------|:---:|------|
| `--border-lw` | 1.8 | 加粗边框，适合论文插图 |
| `--line-width` | 1.8 | 加粗曲线 |
| `--font-size` | 14 | 基础字号 |
| `--legend-fontsize` | 14（≤6 条曲线）/ 10（>6 条） | 图例字号 |
| `--table-fontsize` | 12 | 表格字号 |
| `--table-row-spacing` | 0.03 | 1.5 倍行距 |
| `--no-table-lines` | 推荐 | 无线条表格更清爽 |
| `--transparent-background` | 推荐 | 透明背景，方便拼图 |
| `--no-save-source` | 无需 | 源文件默认自动复制，此参数用于关闭 |

### 叠加模式
- 8×6.4 inches（5:4 比例），300 dpi
- 12 色调色板自动分配
- 左上角：简洁图例（仅线条+标签，无 Mn/PDI）
- 右上角：Mn/PDI 汇总表

### 分图模式
- 5×4 inches（5:4 比例），300 dpi
- 每图独立表格

## 数据解析

### Cirrus Slice_Table

```
<Slice_Table>
RT (mins)	Response	MW	logMW	dw_dlogM	...
```

- 列 0：RT（保留时间）
- 列 6：dw_dlogM（微分分布）
- 基线过滤：`dw_dlogM > 0`
- 归一化：`/ max()` → [0, 1]

### 曲线双向延伸算法（`--extend-tail`）

`--extend-tail` 一个开关控制双向延伸 + 数据写入，两者绑定不可拆分。

#### 头部延伸 → xmin

**三次 Hermite 插值**，强制 y(xmin) = 0：

$$y(t) = y_1 \cdot (-2u^3 + 3u^2) + m_1 \cdot \Delta t \cdot (u^3 - u^2), \quad u = \frac{t - x_{\min}}{\Delta t}$$

边界条件：$(x_{\min}, 0, 0)$ → $(t_1, y_1, m_1)$。$m_1$ 由头部 10 个点的线性回归估计。保证 $y(x_{\min}) = 0$，$y'(x_{\min}) = 0$，接头处 C¹ 连续。

#### 尾部延伸 → xmax

**指数衰减**，锚定末点，强制单调递减：

$$y(t) = y_{\text{last}} \cdot e^{k \cdot (t - t_{\text{last}})}, \quad k < 0$$

$k$ 由尾部 10 个点的 $\ln(y)$ 线性回归确定。若 $k \geq 0$（非单调），回退为 $k = -0.5 / (x_{\max} - t_{\text{last}})$。天然 C⁰ 连续，严格单调递减。

#### 源文件写入

延伸数据反归一化后注入 `sources/` 中转存 `.txt` 的 `Slice_Table`：头部行插入表头后，尾部行插入 `</Slice_Table>` 前。其他列沿用末行模板值，仅 RT（col 0）和 dw_dlogM（col 6）替换为合成值。

### MW 参数

从 `<MW_Averages>` 标签内正则提取 Mp、Mn、Mw、PDI。如有多个峰（如溶剂峰 + 聚合物峰），自动跳过 Mn ≤ 0 的条目，取第一个有效聚合物峰。

### 多峰归一化问题

若 GPC 文件含两个相距很远的峰（溶剂/单体峰 + 聚合物峰），全局归一化会压制聚合物峰。解决方法：用过滤脚本只保留目标 RT 范围的数据行，然后重新运行 `plot_gpc.py`：

```python
# 过滤 Slice_Table 中 RT 24–34 的数据
src = "sources/1.4eq.txt"
# ... 只保留 24 <= RT <= 34 的行 ...
# 然后用过滤后的文件重新跑 plot_gpc.py
```

## 输出配套

画图完成后，建议在每个图目录下放置 `README.txt`，包含中英双语的论文图注（一句即可）：

```
Fig. X GPC overlay of PBA prepared with ...
图 X ......制备 PBA 的 GPC 叠加图。
```

## 兼容性

- **EPS 透明度警告可忽略**：脚本不使用透明元素，但 matplotlib EPS 后端可能仍输出警告，不影响图像质量。
- **字体**：标注用 Arial（默认）。EPS 嵌入 Type 3 字体，自包含。
- **特殊字符**：文件名含 `<>:"/\|?*` 自动替换为 `_`。

## 数据溯源（--save-source）

添加 `--save-source` 后，每个输出子文件夹内会额外生成 `sources/` 目录，存放本次绘图所用的原始 `.txt` 数据文件副本。用于论文投稿时提供可复现的数据源。

```
gpc_overlay/
├── gpc_overlay.eps
├── gpc_overlay.tif
└── sources/              ← --save-source 时生成
    ├── NaF.txt
    ├── NaCl.txt
    ├── NaBr.txt
    └── NaI.txt
```

## 故障排除

| 症状 | 原因 | 解决 |
|------|------|------|
| `format: unknown` | 未知格式 | 读取文件头部，必要时扩展 detect_format |
| `No valid data` | dw_dlogM 全零 | 检查 Slice_Table 数据完整性 |
| 中文乱码 | GBK 控制台 | 设 `PYTHONIOENCODING=utf-8` |
| 图片空白 | 数据超出范围 | 用 `--xmin` / `--xmax` 手动设轴范围 |
| Mn/PDI 值错误 | 正则越界匹配 | 检查 `<MW_Averages>` 标签是否完整闭合 |
| 图例标签是内部长名 | 文件名未改名 | 将文件复制为有意义的短名（如 `NaF.txt`），脚本用文件主名做标签 |
| 多张组图被覆盖 | 叠加模式固定输出名 `gpc_overlay` | 每张图指定不同 `-o` 目录 |
| Mn/PDI 值为 0 | 文件含多峰，匹配到溶剂峰 | 已修复：自动跳过 Mn≤0 的峰；若仍异常，检查 MW_Averages 段 |
| 多峰导致归一化不准 | 溶剂峰过高压制聚合物峰 | 用过滤脚本裁剪 Slice_Table 的目标 RT 范围后重跑 |
| matplotlib 未安装 | 路径不对或 uv 托管 | 用系统 Python 3.12 路径，或 `uv pip install matplotlib` |

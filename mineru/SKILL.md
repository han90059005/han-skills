---
name: mineru
description: '把 PDF / 课件 / 扫描件转成 Markdown，并按需阅读、审校公式。当用户要求"读这份 PDF""快速看看这篇讲什么""把课件转成笔记""提取文献里的公式""这本书扫描件能不能转"时使用。三条路径：文字层文档秒级直读（quickread）、文字层课件的公式页定点渲染核对（A+，默认首选）、复杂/扫描文档走 MinerU 转换。转换后强制剥离 base64 图片，阅读前必须先出结构摘要并由用户确认范围，避免一次性烧掉大量 token。'
argument-hint: '[文件路径]'
---

# MinerU 文档转换与审阅

## 这个技能解决什么

MinerU 能把 PDF 转成 Markdown，但**直接用的两个坑**：

1. 它把插图内嵌成 base64，3 页正文的 md 可达 854 KB（约 20 万 token）
2. 慢——文字层文档也要 20 秒/页，而纯抽取只要毫秒

本技能在它外面包一条带闸门的流水线，并保留一条"秒级直读"的快车道；**文字层课件默认走 A+（秒读 + 公式页定点渲染），不要动辄全量转。**

## 三条红灯（违反就是事故）

1. **永远不要直接读 MinerU 的原始输出 md**。必须先跑 `clean.py` 剥离 base64。
2. **永远不要在没有结构摘要的情况下通读全文**。出完摘要要**停下来**问用户读哪部分。
3. **修改公式前必须出清单等用户确认**。不擅自改文件。

## 环境常量

```powershell
$PY = "D:\AI-tools\mineru\Scripts\python.exe"
$MK = "D:\AI-tools\mineru\Scripts\mineru-kit.exe"
$env:MINERU_HOME = "D:\AI-tools\mineru-home"
$env:PYTHONIOENCODING = "utf-8"   # 必设：否则中文路径显示成 ѧϰ����（见报错对照）
$SC = "C:\Users\admin\.agents\skills\mineru\scripts"
```

---

## 决策：走哪条路

打开 PDF 之前先看两件事：**有没有文字层**（决定 A/A+ 还是 B）、**要"看一眼"还是"要成品"**（决定要不要跑模型）。

| 需求 | 路径 | 耗时 |
|---|---|---|
| 快速扫一眼、找关键词、确认是不是我要的那篇 | **quickread** | < 1 秒 |
| 要引用页码、要能搜索定位 | **quickread**（自带页号） | < 1 秒 |
| **有文字层的课件/讲义：要读懂、要改笔记** | **路径 A+**（quickread 全文 + 公式页定点 render） | 秒级 + 1 秒/页 |
| 要可交付的 LaTeX/表格结构 md 成品、批量入库 | **MinerU 全流程** | 20–30 秒/页 |
| 扫描件 | **MinerU 全流程**（standard） | 同上 |
| 只要看某一页的公式/图 | **render** | 1 秒 |

**先按页数算一笔账再决定要不要跑 MinerU**：20 页 ≈ 8 分钟，70 页 ≈ 半小时，290 页 ≈ 2 小时。十几页以上的文字层文档，全量转几乎总是不划算——把「抽公式、转笔记」直接等同于「MinerU 全流程」是旧版本的错判。

---

## 路径 A · 秒级直读（quickread）

```powershell
& $PY "$SC\quickread.py" "<pdf>" --pages 1-10
```

- 只读文字层，不跑模型
- 自带 `--- 第 N 页 ---` 标记
- **默认最多输出 20000 字符（约 1 万 token）**，超出自动截断并提示分段
- 全空 → 说明是扫描件，脚本会直接提示转路径 B

## 路径 A+ · 文字层课件（最常用，先考虑它）

**适用**：PPT 转 PDF、数字版讲义、有文字层的习题/教材页——正文可读、公式散架的那一类。

```powershell
# 1) 秒读全文；长文档落 txt，再用 read 分段读，别一次灌进上下文
& $PY "$SC\quickread.py" "<pdf>" --all --max-chars 60000 --save
# 2) 只把公式页渲染出来核对（1 秒/页，页范围可用逗号混写）
& $PY "$SC\render.py" "<pdf>" --pages 38-39,57 --out "$env:TEMP\pdfcheck"
```

然后 `read_image` 并行看这几张图，把**核对过的**公式抄进笔记。

- 为什么够用：文字层里正文、术语、结论、页码都是准的，坏的是公式结构与表格。
- 实测（2026-10-26，高分子物理 4 份课件、共 292 页，coverage 0.81~0.94）：全量 MinerU basic 要 1.6~2.4 小时；quickread 秒级拿到全部正文，再 render 3 组 6 页核对，全程 < 1 分钟。
- 校准价值（别省这步）：3 组里 2 组逐字一致，1 组漏了常数项与展开式（Mooney 的 C₁ = ½NkT、λ 展开式被压成不变量式）。**quickread 的公式只能当线索，不能当真。**
- 仍要走路径 B 的情形：需要公式 LaTeX 原文、需要表格结构、产物要交给 makelatex/makedocx 排版；以及扫描件。

## 路径 B · MinerU 全流程

### 第 1 步 · 探测（零 token）

```powershell
& $PY "$SC\probe.py" "<文件>"
```

| 判定 | 条件 | 档位 |
|---|---|---|
| `structured` | 覆盖率 ≥ 0.8 | **basic** |
| `scanned` | 覆盖率 ≤ 0.2 | **standard** |
| `mixed` | 中间 | **standard**（basic 在扫描页会错下标） |
| `office` | pptx/docx/xlsx 等 | **flash** |

### 第 2 步 · 样本（停顿点 ①）

**默认先跑前 5–10 页，不要全量。**

```powershell
& $MK parse "<文件>" -o "<产物目录>\_sample" --tier <档位> --pages 1-10
```

样本跑完 → 第 3、4 步生成摘要 → **拿摘要问用户**：质量可接受吗、要不要跑完整本、跑哪些页。

### 第 3 步 · 清洗（自动，不可跳过）

```powershell
& $PY "$SC\clean.py" "<输出.md>"
```

产出 `<同名>_clean.md`，base64 图片替换为占位注释，并报告剥离前后体积。

**这一步是后面所有 token 控制的前提。读取动作永远只发生在 `_clean.md` 上。**

### 第 4 步 · 结构摘要（约 200 token）

```powershell
& $PY "$SC\outline.py" "<..._clean.md>"
```

输出标题树、公式数、表格数、字符数、token 估算。

### 第 5 步 · 停顿点 ②（最关键）

把摘要交给用户，**停下来**，三选一：

| 选项 | 做法 | 典型代价 |
|---|---|---|
| 只读某章 | 按标题行号定位后 `read` 指定区间 | 1–3k token |
| 只查公式 | `mathreview.py` 抽公式+上下文，正文不读 | ~1k token |
| 全文 | 先报估算，**明确确认后**再分块读 | 5–80k token |

不许自作主张选第三项。

### 第 6 步 · 按需阅读

- 单章：`read` 指定 offset/limit
- 公式：`& $PY "$SC\mathreview.py" <clean.md>`，输出带行号的公式与上下文，并自动标记可疑项
- 全文：分块读，每块出小结后丢弃

### 第 7 步 · 订正（只出清单）

从 `mathreview.py` 的标记里挑出可疑项，按此格式：

```
L110  原：\frac{\int M_n(M)dM}{\int n(M)dM}
      建议：\frac{\int M\,n(M)dM}{\int n(M)dM}
      理由：n(M) 是数量分布函数，M 与其相乘，不是下标
```

用户逐条确认后才改，改前 `Copy-Item x_clean.md x_clean.md.bak`。

### 第 8 步 · 交付与核验

产物放**源文件同目录**：`<原名>_clean.md`、`<原名>_report.md`。

公式存疑时，渲染原页直接看（**临时核对输出到 TEMP，别污染资料目录**）：

```powershell
& $PY "$SC\render.py" "<pdf>" --pages 150-152 --out "$env:TEMP\pdfcheck"
```

然后用 `read_image` 看图（可一次并行读多张），人工/AI 直接读公式——这比任何 OCR 都准。核对完删掉 TEMP 目录。

---

## 脚本清单

| 脚本 | 作用 |
|---|---|
| `probe.py` | 页数、文字层覆盖率、推荐档位 |
| `quickread.py` | 秒级抽文字层，带页号与 token 闸门 |
| `clean.py` | 剥离 base64 图片 |
| `outline.py` | 结构摘要（标题树、公式/表格计数、token 估算） |
| `mathreview.py` | 只抽公式 + 可疑特征标记 |
| `render.py` | 页面渲染成 PNG，供视觉核对 |

---

## 命名与位置约定

| 内容 | 位置 |
|---|---|
| 原始输出 | 源文件同目录 `_mineru_raw/` |
| 清洗后 | 源文件同目录 `<原名>_clean.md` |
| 质量报告 | 源文件同目录 `<原名>_report.md` |
| 渲染页（临时核对） | `$env:TEMP\pdfcheck\`，用完删 |
| 渲染页（要交付的图） | 才放源文件同目录 `<原名>_pages/` |

课件、资料、笔记目录默认只放源文件与最终产物——渲染图是过程物，别留在人家文件夹里。

---

## 档位实测记录（本机 4060 Laptop 8 GB）

| 文档 | 页数 | basic | standard |
|---|---|---|---|
| LaTeX 排版习题 | 3 | 66 s，公式 7/7 全对 | 未测 |
| 数字版课件（带装饰框） | 10 | 54 s，4 处问题 | 39 s，**9 处 `\left|`/`\boxed` 幻觉** |
| 论文正文（文本层） | 3 | 19.5 s | 25.6 s，输出逐字节相同 |
| 扫描版教材 | 3 | 26.5 s，下标错、正文入公式 | 26.4 s，**下标正确、边界干净** |
| 高分子物理课件（PPT 转 PDF，4 份） | 292 | **未跑**（约 2 h，不值） | 未跑 |

最后一行的处理方式即路径 A+：quickread 全文 + 6 页 render 核对，< 1 分钟；正文全对，公式 2/3 全对、1/3 需目视补常数项。

**规律：有文字层用 basic，纯图像用 standard；页数 × 25 s 算一算，超 20 页先考虑 A+。**

**页数以 `probe.py` / `render.py`（pypdfium2）为准**：`pdftotext` 按换页符切会在尾部多出一页空壳（69 页的 PDF 数成 70），引用页码时别被它带偏。

---

## 两档共有的已知缺陷（审校重点）

- 加粗丢失、标题层级压平、列表顺序可能错乱
- 破折号丢失导致句子粘连
- 中文全角冒号变半角、`~` 变 `∼`
- 公式下标归属错误（`M\,n(M)` → `M_n(M)` 这类），**最隐蔽**
- standard 会把装饰边框认成 `\left|`、`\boxed`
- 变量常被写成正体 `\mathrm{M}`

## 已知风险

- standard 档 8 GB 显存是门槛下限，长文档可能 `parse_oom`，报错就减 `--pages`
- `quickread` 的公式会散架：常数/系数丢失、积分上下限拆成独立行、上下标错位、`∑`/`∫` 与主体分离。正文和结论可信，公式只当线索——关键式必须 render 目视核对
- 课件类 PDF 的页脚常混进正文（`第七章-1`、页码 43 之类），抽取后要随手剔掉，别照抄进笔记

## 报错对照

| 报错 | 对策 |
|---|---|
| `本地 mineru 服务未运行` | 用 `mineru-kit`，不是 `mineru` |
| `parse_oom` | 减页数或降档 |
| 找不到模型 | 检查 `MINERU_HOME` |
| `exit code 1` 但文件已生成 | PowerShell 把 stderr 当错误，看产物在不在 |
| `quickread` 输出全空 | 扫描件，走路径 B |
| 中文路径显示成 `ѧϰ����`、`��ҳ��` | 先 `$env:PYTHONIOENCODING="utf-8"`（实测：设 `[Console]::OutputEncoding` 无效）。乱码不影响脚本干活，`verdict`/`tier` 等 ASCII 字段照读 |
| 页数比 `pdftotext` 统计少 1 | 正常，pdftotext 尾部多一页空壳；页码一律以 probe/render 为准 |

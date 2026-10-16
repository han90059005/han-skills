---
name: makedocx
description: '将 Markdown、LaTeX 或 XeLaTeX 文档转换为符合中文论文规范的完整 Microsoft Word（.docx）文件。应用正确的字体（宋体、Times New Roman、Arial）、标题字号（三号/四号/小四）、1.5 倍行距、图表标题格式、三线表、OMML 公式和参考文献格式。核心是 pandoc 转换 + python-docx 后处理，侧重最终 Word 排版输出；生成复习笔记用 course-review-generator，依据文献写论文用 makepaper，转中文 PDF 用 makelatex。'
user-invocable: true
argument-hint: '[path to .md or .tex file]'
---

# Markdown / LaTeX / XeLaTeX → Word 学术文档转换

## 概述

将用户提供的 Markdown、LaTeX 或 XeLaTeX 源文件完整转换为 Microsoft Word（.docx）格式文档，严格遵循中国学术论文、毕业论文及 SCI 期刊投稿的常见排版规范。

## 与其他技能的区别

- 本技能只负责「Markdown / LaTeX → Word（.docx）」的最终排版，不负责内容生成。
- 复习笔记生成/合并 → course-review-generator；依据文献写论文 → makepaper；Markdown 转中文 PDF → makelatex。

## 运行可靠性

- 先确认 `pandoc --version` ≥ 3.0；python-docx 用 `uv run --with python-docx` 临时安装，不污染系统环境。
- 目标 `.docx` 被 Word 占用报 Permission denied 时，另存为新文件名再处理。
- 转换后校验：docx 能正常打开，标题字号、三线表、公式、参考文献保留；路径含中文/空格时用引号包裹。

## 触发条件

- 用户要求将 `.md` / `.tex` 转为 `.docx`
- 用户要求按学术论文格式排版 Word 文档
- 用户提到"三线表"、"宋体小四"、"黑体三号"等中文学术排版术语
- 用户要求生成投稿级 Word 文档

## 核心原则

1. **保持原文内容完整**，不得遗漏、增删或擅自改写内容
2. **保持原有章节结构**、标题层级、编号体系及交叉引用关系
3. **保持数学公式、图片、表格、参考文献、脚注**等元素的完整性
4. 输出语言与原文一致；若用户指定中文或英文，则统一转换为指定语言
5. 文档最终格式应符合学术论文、毕业论文或 SCI 期刊投稿的常见规范

---

## 标题与字号规范

### 正文

| 属性 | 规范 |
|------|------|
| 中文字体 | 宋体（SimSun） |
| 英文字体 | Times New Roman |
| 字号 | 小四（12 pt） |
| 字体颜色 | 黑色（RGB 0,0,0） |
| 行距 | 1.5 倍行距 |
| 对齐方式 | 两端对齐（Justify） |
| 首行缩进 | 中文正文首行缩进 2 个字符 |

### 一级标题

格式示例：`# 1 绪论`

| 属性 | 规范 |
|------|------|
| 中文字体 | 黑体（SimHei） |
| 英文字体 | Times New Roman |
| 字号 | 三号（16 pt） |
| 加粗 | 是 |
| 对齐方式 | 居中 |
| 段前间距 | 18 pt |
| 段后间距 | 12 pt |

### 二级标题

格式示例：`## 1.1 实验部分`

| 属性 | 规范 |
|------|------|
| 中文字体 | 黑体（SimHei） |
| 英文字体 | Times New Roman |
| 字号 | 四号（14 pt） |
| 加粗 | 是 |
| 对齐方式 | 左对齐 |
| 段前间距 | 12 pt |
| 段后间距 | 6 pt |

### 三级标题

格式示例：`### 1.1.1 原料与试剂`

| 属性 | 规范 |
|------|------|
| 中文字体 | 黑体（SimHei） |
| 英文字体 | Times New Roman |
| 字号 | 小四（12 pt） |
| 加粗 | 是 |
| 对齐方式 | 左对齐 |
| 段前间距 | 6 pt |
| 段后间距 | 3 pt |

### 四级标题（如存在）

格式示例：`#### （1）实验步骤`

| 属性 | 规范 |
|------|------|
| 中文字体 | 宋体（SimSun） |
| 英文字体 | Times New Roman |
| 字号 | 小四（12 pt） |
| 加粗 | 是 |
| 对齐方式 | 左对齐 |

---

## 图题

| 属性 | 规范 |
|------|------|
| 中文字体 | 宋体（SimSun） |
| 英文字体 | Times New Roman |
| 字号 | 五号（10.5 pt） |
| 对齐方式 | 居中 |
| 位置 | 图片下方 |

示例：

> 图 1 PBA 聚合机理
>
> Figure 1 Polymerization mechanism of PBA

---

## 表题

| 属性 | 规范 |
|------|------|
| 中文字体 | 宋体（SimSun） |
| 英文字体 | Times New Roman |
| 字号 | 五号（10.5 pt） |
| 对齐方式 | 居中 |
| 位置 | 表格上方 |

示例：

> 表 1 聚合结果统计
>
> Table 1 Polymerization results

---

## 表格内容

| 属性 | 规范 |
|------|------|
| 中文字体 | 宋体（SimSun） |
| 英文/数字字体 | Arial |
| 字号 | 五号（10.5 pt） |

### 三线表规范

表格采用中国学术标准三线表格式：

- **顶线**：1.5 pt 粗线
- **表头下线**：1 pt 细线
- **底线**：1.5 pt 粗线
- **无竖线**、**无内部横线**

---

## 公式

| 属性 | 规范 |
|------|------|
| 格式 | Word 原生公式对象（OMML） |
| 对齐方式 | 公式居中，编号右对齐 |
| 变量字体 | Times New Roman 斜体 |
| 字号 | 与正文一致（12 pt） |

> ⚠️ 公式必须使用 Word 原生公式编辑器（OMML 格式），不可使用图片或 MathType。

---

## 参考文献

| 属性 | 规范 |
|------|------|
| 中文字体 | 宋体（SimSun） |
| 英文字体 | Times New Roman |
| 字号 | 小五（9 pt） |
| 缩进 | 悬挂缩进 2 字符 |
| 行距 | 单倍行距 |

---

## 工作流程

### Phase 1: 源文件判断

根据输入文件类型选择转换路径：

```
输入文件类型？
├── .md (Markdown)
│   └── 使用 Pandoc 转换 + python-docx 后处理
│
├── .tex (LaTeX / XeLaTeX)
│   └── 使用 Pandoc (xelatex 引擎) 转换 + python-docx 后处理
│
└── 其他
    └── 先尝试 Pandoc，失败则告知用户
```

### Phase 2: Pandoc 初步转换

#### Markdown → Docx

```powershell
pandoc "path\to\file.md" -o "path\to\file.docx" --from=markdown+tex_math_dollars --resource-path="path\to\file_dir"
```

#### LaTeX/XeLaTeX → Docx

```powershell
pandoc "path\to\file.tex" -o "path\to\file.docx" --pdf-engine=xelatex --resource-path="path\to\file_dir"
```

常用 Pandoc 参数说明：

| 参数 | 用途 |
|------|------|
| `--from=markdown+tex_math_dollars` | 支持 `$...$` 和 `$$...$$` 数学公式 |
| `--resource-path` | 指定图片等资源搜索路径 |
| `--pdf-engine=xelatex` | 指定 XeLaTeX 引擎 |
| `--reference-doc` | 使用自定义模板 docx（可选） |

### Phase 3: Python 后处理（python-docx）

Pandoc 生成的 docx 使用默认样式，需要 python-docx 后处理施加完整排版规范。

```powershell
uv run --with python-docx python "<format_script.py>" "<input.docx>" "<output.docx>"
```

### Phase 4: 自动格式检查

转换完成后必须逐一检查以下项目：

- [ ] ✓ 正文字号是否为小四（12 pt）
- [ ] ✓ 一级标题是否为三号（16 pt）加粗居中
- [ ] ✓ 二级标题是否为四号（14 pt）加粗
- [ ] ✓ 三级标题是否为小四（12 pt）加粗
- [ ] ✓ 全文是否为纯黑色字体（RGB 0,0,0）
- [ ] ✓ 中文是否为宋体（SimSun）
- [ ] ✓ 英文是否为 Times New Roman
- [ ] ✓ 表格英文/数字是否为 Arial
- [ ] ✓ 表格是否符合三线表规范（2 pt / 1 pt / 2 pt）
- [ ] ✓ 所有公式是否可编辑（OMML 格式）
- [ ] ✓ 图片与参考文献是否完整保留
- [ ] ✓ 正文行距是否为 1.5 倍
- [ ] ✓ 中文正文首行是否缩进 2 字符

---

## Python 格式化脚本参考

脚本应与本 SKILL.md 同目录存放，命名为 `format_academic_docx.py`。

### 核心格式化函数

```python
from docx import Document
from docx.shared import Pt, Cm, Inches, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml
import copy
import re

# 字体配置
SIMSUM = '宋体'
SIMHEI = '黑体'
TIMES_NEW_ROMAN = 'Times New Roman'
ARIAL = 'Arial'

# 字号配置（Pt）
SIZE_SAN_HAO = Pt(16)      # 三号 — 一级标题
SIZE_SI_HAO = Pt(14)       # 四号 — 二级标题
SIZE_XIAO_SI = Pt(12)      # 小四 — 正文、三级标题、四级标题、公式
SIZE_WU_HAO = Pt(10.5)     # 五号 — 图题、表题、表格内容
SIZE_XIAO_WU = Pt(9)       # 小五 — 参考文献

BLACK = RGBColor(0, 0, 0)


def set_run_font(run, cn_font=None, en_font=None, size=None, bold=None, color=BLACK):
    """设置 run 的中英文字体、字号、加粗和颜色"""
    if cn_font:
        run.font.name = cn_font
        r = run._element
        rPr = r.find(qn('w:rPr'))
        if rPr is None:
            rPr = parse_xml(f'<w:rPr {nsdecls("w")}></w:rPr>')
            r.insert(0, rPr)
        rFonts = rPr.find(qn('w:rFonts'))
        if rFonts is None:
            rFonts = parse_xml(f'<w:rFonts {nsdecls("w")}></w:rFonts>')
            rPr.insert(0, rFonts)
    if en_font or cn_font:
        rFonts = rPr.find(qn('w:rFonts'))
        if rFonts is None:
            rFonts = parse_xml(f'<w:rFonts {nsdecls("w")}></w:rFonts>')
            rPr.insert(0, rFonts)
        if en_font:
            rFonts.set(qn('w:ascii'), en_font)
            rFonts.set(qn('w:hAnsi'), en_font)
            rFonts.set(qn('w:eastAsia'), cn_font or en_font)
    if size:
        run.font.size = size
    if bold is not None:
        run.bold = bold
    run.font.color.rgb = color


def set_paragraph_spacing(paragraph, before=None, after=None, line_spacing=None):
    """设置段落间距和行距"""
    pf = paragraph.paragraph_format
    if before is not None:
        pf.space_before = before
    if after is not None:
        pf.space_after = after
    if line_spacing is not None:
        pf.line_spacing = line_spacing


def apply_three_line_table(table):
    """对单个表格施加三线表边框：顶线 2pt、表头下线 1pt、底线 2pt，无竖线无内部横线"""
    tbl = table._tbl
    tblPr = tbl.find(qn('w:tblPr'))
    if tblPr is None:
        tblPr = parse_xml(f'<w:tblPr {nsdecls("w")}></w:tblPr>')
        tbl.insert(0, tblPr)

    # 清除所有默认边框
    borders_to_remove = tblPr.findall(qn('w:tblBorders'))
    for b in borders_to_remove:
        tblPr.remove(b)

    # 创建三线表边框定义
    borders_xml = (
        f'<w:tblBorders {nsdecls("w")}>'
        f'  <w:top w:val="single" w:sz="24" w:space="0" w:color="000000"/>'   # 2pt = 24 eighths
        f'  <w:left w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        f'  <w:bottom w:val="single" w:sz="24" w:space="0" w:color="000000"/>' # 2pt = 24 eighths
        f'  <w:right w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        f'  <w:insideH w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        f'  <w:insideV w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(parse_xml(borders_xml))

    # 表头下行：1pt 细线（仅第一行单元格底部）
    if len(table.rows) > 0:
        for cell in table.rows[0].cells:
            tcPr = cell._tc.find(qn('w:tcPr'))
            if tcPr is None:
                tcPr = parse_xml(f'<w:tcPr {nsdecls("w")}></w:tcPr>')
                cell._tc.insert(0, tcPr)
            tcBorders = tcPr.find(qn('w:tcBorders'))
            if tcBorders is None:
                tcBorders = parse_xml(f'<w:tcBorders {nsdecls("w")}></w:tcBorders>')
                tcPr.append(tcBorders)
            bottom = parse_xml(
                f'<w:bottom {nsdecls("w")} w:val="single" w:sz="12" w:space="0" w:color="000000"/>'
            )
            existing = tcBorders.find(qn('w:bottom'))
            if existing is not None:
                tcBorders.remove(existing)
            tcBorders.append(bottom)


def format_academic_docx(input_path, output_path):
    """主函数：读取 Pandoc 生成的 docx，施加完整学术排版格式"""
    doc = Document(input_path)

    # 遍历所有段落，根据样式和内容判断层级
    for para in doc.paragraphs:
        style_name = para.style.name if para.style else ''
        text = para.text.strip()

        # 判断标题层级（Pandoc 生成的样式名如 "Heading 1", "Heading 2" 等）
        if style_name.startswith('Heading 1') or style_name == 'heading 1':
            _format_heading_level_1(para)
        elif style_name.startswith('Heading 2') or style_name == 'heading 2':
            _format_heading_level_2(para)
        elif style_name.startswith('Heading 3') or style_name == 'heading 3':
            _format_heading_level_3(para)
        elif style_name.startswith('Heading 4') or style_name == 'heading 4':
            _format_heading_level_4(para)
        else:
            # 正文段落
            _format_body(para)

    # 格式化表格
    for table in doc.tables:
        apply_three_line_table(table)
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    for run in para.runs:
                        set_run_font(run, cn_font=SIMSUM, en_font=ARIAL, size=SIZE_WU_HAO)

    doc.save(output_path)


def _format_heading_level_1(para):
    """一级标题：黑体 三号(16pt) 加粗 居中 段前18pt 段后12pt"""
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_spacing(para, before=Pt(18), after=Pt(12), line_spacing=1.5)
    for run in para.runs:
        set_run_font(run, cn_font=SIMHEI, en_font=TIMES_NEW_ROMAN, size=SIZE_SAN_HAO, bold=True)


def _format_heading_level_2(para):
    """二级标题：黑体 四号(14pt) 加粗 左对齐 段前12pt 段后6pt"""
    para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_paragraph_spacing(para, before=Pt(12), after=Pt(6), line_spacing=1.5)
    for run in para.runs:
        set_run_font(run, cn_font=SIMHEI, en_font=TIMES_NEW_ROMAN, size=SIZE_SI_HAO, bold=True)


def _format_heading_level_3(para):
    """三级标题：黑体 小四(12pt) 加粗 左对齐 段前6pt 段后3pt"""
    para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_paragraph_spacing(para, before=Pt(6), after=Pt(3), line_spacing=1.5)
    for run in para.runs:
        set_run_font(run, cn_font=SIMHEI, en_font=TIMES_NEW_ROMAN, size=SIZE_XIAO_SI, bold=True)


def _format_heading_level_4(para):
    """四级标题：宋体 小四(12pt) 加粗 左对齐"""
    para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for run in para.runs:
        set_run_font(run, cn_font=SIMSUM, en_font=TIMES_NEW_ROMAN, size=SIZE_XIAO_SI, bold=True)


def _format_body(para):
    """正文：宋体/Times New Roman 小四(12pt) 两端对齐 1.5倍行距 首行缩进2字符"""
    para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    pf = para.paragraph_format
    pf.line_spacing = 1.5
    # 首行缩进 2 字符 ≈ 24 pt（小四字号下 2 字符 ≈ 24 pt）
    pf.first_line_indent = Pt(24)
    for run in para.runs:
        set_run_font(run, cn_font=SIMSUM, en_font=TIMES_NEW_ROMAN, size=SIZE_XIAO_SI)


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print("Usage: uv run --with python-docx python format_academic_docx.py <input.docx> <output.docx>")
        sys.exit(1)
    format_academic_docx(sys.argv[1], sys.argv[2])
    print(f"✅ 格式化完成: {sys.argv[2]}")
```

---

## 文件被锁时的处理

若 `.docx` 被 Word 占用导致 `Permission denied`：

```powershell
uv run --with python-docx python "format_academic_docx.py" "input.docx" "output_已排版.docx"
```

---

## 前置依赖

安装前确认：

```powershell
pandoc --version          # Pandoc ≥ 3.0
uv --version              # uv Python 包管理器
```

若缺少 Pandoc：

```powershell
winget install --id JohnMacFarlane.Pandoc
```

---

## 注意事项

- Pandoc 生成的 docx 默认使用 Calibri 等英文字体，**必须**通过 python-docx 后处理替换为中文学术字体
- 公式在 Pandoc 转换时优先保留为 OMML 格式；若源文件使用 `$...$` 内联公式，需加 `--from=markdown+tex_math_dollars`
- 中文路径和文件名需用双引号包裹
- python-docx 临时安装使用 `uv run --with python-docx`，不污染系统 Python 环境
- 首行缩进 2 字符在小四（12 pt）字号下 ≈ 24 pt；若正文使用其他字号需按比例调整
- 表格三线表边框的 `w:sz` 单位是 1/8 pt：24 = 2pt, 12 = 1pt

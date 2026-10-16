"""
Academic Document Formatter — 学术文档排版脚本

将 Pandoc 生成的 .docx 施加完整的中文学术排版规范：
- 标题层级字体/字号/间距
- 正文宋体小四 1.5 倍行距 首行缩进
- 三线表边框
- 图题/表题格式化
"""

from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml

# ── 字体常量 ────────────────────────────────────────────
SIMSUM = '宋体'
SIMHEI = '黑体'
TIMES_NEW_ROMAN = 'Times New Roman'
ARIAL = 'Arial'

# ── 字号常量 ────────────────────────────────────────────
SIZE_SAN_HAO = Pt(16)       # 三号 — 一级标题
SIZE_SI_HAO = Pt(14)        # 四号 — 二级标题
SIZE_XIAO_SI = Pt(12)       # 小四 — 正文、三级标题、四级标题、公式
SIZE_WU_HAO = Pt(10.5)      # 五号 — 图题、表题、表格内容
SIZE_XIAO_WU = Pt(9)        # 小五 — 参考文献

BLACK = RGBColor(0, 0, 0)


# ── 辅助函数 ────────────────────────────────────────────

def set_run_font(run, cn_font=None, en_font=None, size=None, bold=None, italic=None, color=BLACK):
    """设置 run 的中英文字体、字号、加粗、斜体和颜色"""
    r = run._element
    rPr = r.find(qn('w:rPr'))
    if rPr is None:
        rPr = parse_xml(f'<w:rPr {nsdecls("w")}></w:rPr>')
        r.insert(0, rPr)

    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = parse_xml(f'<w:rFonts {nsdecls("w")}></w:rFonts>')
        rPr.insert(0, rFonts)

    if en_font:
        rFonts.set(qn('w:ascii'), en_font)
        rFonts.set(qn('w:hAnsi'), en_font)
        rFonts.set(qn('w:cs'), en_font)
    if cn_font:
        rFonts.set(qn('w:eastAsia'), cn_font)
    elif en_font:
        rFonts.set(qn('w:eastAsia'), en_font)

    if cn_font:
        run.font.name = cn_font

    if size:
        run.font.size = size
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.font.italic = italic
    run.font.color.rgb = color


def set_paragraph_spacing(para, before=None, after=None, line_spacing=None):
    """设置段落间距和行距"""
    pf = para.paragraph_format
    if before is not None:
        pf.space_before = before
    if after is not None:
        pf.space_after = after
    if line_spacing is not None:
        pf.line_spacing = line_spacing


def apply_three_line_table(table):
    """
    对单个表格施加三线表边框：
    - 顶线：1.5pt (sz=18)
    - 表头下线：1pt (sz=12)
    - 底线：1.5pt (sz=18)
    - 无竖线、无内部横线
    """
    tbl = table._tbl
    tblPr = tbl.find(qn('w:tblPr'))
    if tblPr is None:
        tblPr = parse_xml(f'<w:tblPr {nsdecls("w")}></w:tblPr>')
        tbl.insert(0, tblPr)

    # 清除旧边框
    for old in tblPr.findall(qn('w:tblBorders')):
        tblPr.remove(old)

    borders_xml = (
        f'<w:tblBorders {nsdecls("w")}>'
        f'  <w:top w:val="single" w:sz="18" w:space="0" w:color="000000"/>'
        f'  <w:left w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        f'  <w:bottom w:val="single" w:sz="18" w:space="0" w:color="000000"/>'
        f'  <w:right w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        f'  <w:insideH w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        f'  <w:insideV w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(parse_xml(borders_xml))

    # 表头下行：1pt 细线
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
            existing = tcBorders.find(qn('w:bottom'))
            if existing is not None:
                tcBorders.remove(existing)
            tcBorders.append(parse_xml(
                f'<w:bottom {nsdecls("w")} w:val="single" w:sz="12" w:space="0" w:color="000000"/>'
            ))


def is_caption_paragraph(para):
    """
    检测是否为图题/表题段落。
    Pandoc 生成的图文标题通常以 'Image: ' 或包含 '图 '、'表 '、'Figure '、'Table ' 开头。
    """
    text = para.text.strip()
    patterns = [
        r'^图\s*\d+', r'^Figure\s+\d+',
        r'^表\s*\d+', r'^Table\s+\d+',
        r'^Image:', r'^Figure:', r'^Table:',
    ]
    for pat in patterns:
        import re
        if re.match(pat, text):
            return True
    return False


def is_reference_section(para):
    """检测是否为参考文献条目"""
    text = para.text.strip()
    # 参考文献常用标记
    if text.startswith('[') and ']' in text[:10]:
        return True
    if text.lower().startswith('reference'):
        return True
    if '参考文献' in text:
        return True
    return False


# ── 格式化函数 ──────────────────────────────────────────

def _fmt_head1(para):
    """一级标题：黑体 三号(16pt) 加粗 居中 段前18pt 段后12pt"""
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_spacing(para, before=Pt(18), after=Pt(12), line_spacing=1.5)
    for run in para.runs:
        set_run_font(run, cn_font=SIMHEI, en_font=TIMES_NEW_ROMAN, size=SIZE_SAN_HAO, bold=True)


def _fmt_head2(para):
    """二级标题：黑体 四号(14pt) 加粗 左对齐 段前12pt 段后6pt"""
    para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_paragraph_spacing(para, before=Pt(12), after=Pt(6), line_spacing=1.5)
    for run in para.runs:
        set_run_font(run, cn_font=SIMHEI, en_font=TIMES_NEW_ROMAN, size=SIZE_SI_HAO, bold=True)


def _fmt_head3(para):
    """三级标题：黑体 小四(12pt) 加粗 左对齐 段前6pt 段后3pt"""
    para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_paragraph_spacing(para, before=Pt(6), after=Pt(3), line_spacing=1.5)
    for run in para.runs:
        set_run_font(run, cn_font=SIMHEI, en_font=TIMES_NEW_ROMAN, size=SIZE_XIAO_SI, bold=True)


def _fmt_head4(para):
    """四级标题：宋体 小四(12pt) 加粗 左对齐"""
    para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for run in para.runs:
        set_run_font(run, cn_font=SIMSUM, en_font=TIMES_NEW_ROMAN, size=SIZE_XIAO_SI, bold=True)


def _fmt_body(para):
    """正文：宋体/Times New Roman 小四(12pt) 两端对齐 1.5倍行距 首行缩进2字符"""
    para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    pf = para.paragraph_format
    pf.line_spacing = 1.5
    pf.first_line_indent = Pt(24)  # 小四字号下 2 字符 ≈ 24 pt
    for run in para.runs:
        set_run_font(run, cn_font=SIMSUM, en_font=TIMES_NEW_ROMAN, size=SIZE_XIAO_SI)


def _fmt_caption(para):
    """图题/表题：宋体/Times New Roman 五号(10.5pt) 居中"""
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in para.runs:
        set_run_font(run, cn_font=SIMSUM, en_font=TIMES_NEW_ROMAN, size=SIZE_WU_HAO)


def _fmt_reference(para):
    """参考文献：宋体/Times New Roman 小五(9pt) 悬挂缩进2字符 单倍行距"""
    pf = para.paragraph_format
    pf.line_spacing = 1.0
    pf.first_line_indent = Pt(-24)  # 悬挂缩进：负首行缩进
    # 左缩进补偿
    from docx.shared import Cm
    pf.left_indent = Cm(0.74)  # 约 2 字符
    for run in para.runs:
        set_run_font(run, cn_font=SIMSUM, en_font=TIMES_NEW_ROMAN, size=SIZE_XIAO_WU)


def _fmt_table_content(table):
    """表格内容：宋体/Arial 五号(10.5pt)"""
    for row in table.rows:
        for cell in row.cells:
            for para in cell.paragraphs:
                for run in para.runs:
                    set_run_font(run, cn_font=SIMSUM, en_font=ARIAL, size=SIZE_WU_HAO)


# ── 主入口 ──────────────────────────────────────────────

def format_academic_docx(input_path, output_path, verbose=False):
    """
    主函数：读取 Pandoc 生成的 docx，施加完整学术排版格式。

    处理顺序：
    1. 段落格式化（标题、正文、图题表题、参考文献）
    2. 表格格式化（三线表 + 内容字体）
    """
    doc = Document(input_path)

    # ── 1. 段落格式化 ──
    heading_map = {
        ('Heading 1', 'heading 1', '1'): _fmt_head1,
        ('Heading 2', 'heading 2', '2'): _fmt_head2,
        ('Heading 3', 'heading 3', '3'): _fmt_head3,
        ('Heading 4', 'heading 4', '4'): _fmt_head4,
    }

    for para in doc.paragraphs:
        style_name = (para.style.name if para.style else '').lower()

        # 判断标题层级
        matched = False
        for keys, fmt_func in heading_map.items():
            if any(k in style_name for k in keys):
                fmt_func(para)
                matched = True
                break

        if matched:
            continue

        # 判断图题/表题
        if is_caption_paragraph(para):
            _fmt_caption(para)
            continue

        # 判断参考文献
        if is_reference_section(para):
            _fmt_reference(para)
            continue

        # 默认：正文
        _fmt_body(para)

    # ── 2. 表格格式化 ──
    for table in doc.tables:
        apply_three_line_table(table)
        _fmt_table_content(table)

    # ── 3. 保存 ──
    doc.save(output_path)

    if verbose:
        print(f"✅ 格式化完成: {output_path}")

    # ── 4. 输出检查清单 ──
    if verbose:
        print("""
📋 格式检查清单：
  ✓ 正文字号是否为小四（12 pt）
  ✓ 一级标题是否为三号（16 pt）加粗居中
  ✓ 二级标题是否为四号（14 pt）加粗
  ✓ 三级标题是否为小四（12 pt）加粗
  ✓ 全文是否为纯黑色字体
  ✓ 中文是否为宋体（SimSun）
  ✓ 英文是否为 Times New Roman
  ✓ 表格英文/数字是否为 Arial
  ✓ 表格是否符合三线表规范（2pt/1pt/2pt）
  ✓ 公式是否可编辑（OMML）
  ✓ 图片与参考文献是否完整保留
  ✓ 正文行距是否为 1.5 倍
  ✓ 中文正文首行是否缩进 2 字符
""")


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print("Usage: uv run --with python-docx python format_academic_docx.py <input.docx> <output.docx>")
        print("Example: uv run --with python-docx python format_academic_docx.py paper.docx paper_formatted.docx")
        sys.exit(1)
    format_academic_docx(sys.argv[1], sys.argv[2], verbose=True)

# -*- coding: utf-8 -*-
"""docx 收尾：图片段落居中、拉丁字体回写、表格列宽、页脚页码、A4 页面。

用法：
    python postprocess_docx.py in.docx out.docx [--a4] [--page-number]
                               [--table-widths 2.4,6.7,6.7] [--header-bold]

为什么要它（format_academic_docx.py 管不到的三件事）：
1. pandoc 把插图放在普通段落里，会被正文样式套上「首行缩进 24 pt + 两端对齐」，
   图整体右移；这里按 w:drawing 识别图片段落，改为居中、零缩进。
2. format_academic_docx.py 里 run.font.name 会把英文/数字字体改成中文字体，
   这里统一把 w:ascii / w:hAnsi 写回 Times New Roman（中文 eastAsia 不动）。
3. 表格列宽与页脚页码：--table-widths 给固定列宽（cm），--page-number 插 PAGE 域。
"""
import argparse

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Cm, Pt

LATIN = "Times New Roman"

PAGE_FIELD = (
    '<w:p %s><w:pPr><w:jc w:val="center"/></w:pPr>'
    '<w:fldSimple w:instr=" PAGE "><w:r><w:t>1</w:t></w:r></w:fldSimple></w:p>'
    % nsdecls("w")
)


def has_drawing(paragraph):
    return bool(paragraph._p.findall(".//" + qn("w:drawing")))


def fix_latin(paragraphs):
    for p in paragraphs:
        for run in p.runs:
            rPr = run._element.get_or_add_rPr()
            rFonts = rPr.find(qn("w:rFonts"))
            if rFonts is None:
                rFonts = parse_xml('<w:rFonts %s/>' % nsdecls("w"))
                rPr.insert(0, rFonts)
            rFonts.set(qn("w:ascii"), LATIN)
            rFonts.set(qn("w:hAnsi"), LATIN)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--a4", action="store_true", help="页面设为 A4 21x29.7 cm")
    ap.add_argument("--page-number", action="store_true", help="页脚居中页码域")
    ap.add_argument("--table-widths", default="", help="逗号分隔列宽，单位 cm，如 2.4,6.7,6.7")
    ap.add_argument("--header-bold", action="store_true", help="表头行加粗")
    ap.add_argument("--caption-prefix", default="图 ", help="图题段落前缀（默认 '图 '）")
    args = ap.parse_args()

    doc = Document(args.src)

    if args.a4:
        for section in doc.sections:
            section.page_width = Cm(21.0)
            section.page_height = Cm(29.7)
            section.top_margin = Cm(2.54)
            section.bottom_margin = Cm(2.54)
            section.left_margin = Cm(2.6)
            section.right_margin = Cm(2.6)

    for para in doc.paragraphs:
        pf = para.paragraph_format
        text = para.text.strip()
        if has_drawing(para):
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            pf.first_line_indent = Pt(0)
            pf.left_indent = Pt(0)
            pf.space_before = Pt(8)
            pf.space_after = Pt(2)
            continue
        if text.startswith(args.caption_prefix):
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            pf.first_line_indent = Pt(0)
            pf.space_before = Pt(0)
            pf.space_after = Pt(10)

    widths = [Cm(float(x)) for x in args.table_widths.split(",") if x.strip()]
    for table in doc.tables:
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        if widths:
            table.autofit = False
        for row in table.rows:
            for i, cell in enumerate(row.cells):
                if widths and i < len(widths):
                    cell.width = widths[i]
                for p in cell.paragraphs:
                    p.paragraph_format.first_line_indent = Pt(0)
                    p.paragraph_format.line_spacing = 1.15
        if args.header_bold:
            for cell in table.rows[0].cells:
                for p in cell.paragraphs:
                    for run in p.runs:
                        run.bold = True

    fix_latin(doc.paragraphs)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                fix_latin(cell.paragraphs)

    if args.page_number:
        for section in doc.sections:
            footer = section.footer
            p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
            p._p.addnext(parse_xml(PAGE_FIELD))
            footer.paragraphs[0].text = ""

    doc.save(args.dst)
    print("saved", args.dst)


if __name__ == "__main__":
    main()

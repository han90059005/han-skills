"""Apply three-line table (三线表) formatting to all tables in a docx file.

Usage:
    uv run --with python-docx python format_three_line.py <input.docx> <output.docx>

三线表 standard:
    - Top: 1.5pt single line
    - Header bottom: 0.75pt single line
    - Bottom: 1.5pt single line
    - No vertical borders, no internal horizontal borders
"""
import sys
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


def set_cell_border(cell, **kwargs):
    """Set cell border.

    Usage:
        set_cell_border(cell,
            bottom={"sz": "6", "val": "single", "color": "000000", "space": "0"}
        )
    """
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement('w:tcBorders')
    for edge in ('start', 'top', 'end', 'bottom', 'insideH', 'insideV'):
        if edge in kwargs:
            element = OxmlElement(f'w:{edge}')
            for attr, val in kwargs[edge].items():
                element.set(qn(f'w:{attr}'), str(val))
            tcBorders.append(element)
    for existing in tcPr.findall(qn('w:tcBorders')):
        tcPr.remove(existing)
    tcPr.append(tcBorders)


def apply_three_line_table(table):
    """Apply 三线表 formatting to a table."""
    tbl = table._tbl
    tblPr = tbl.tblPr if tbl.tblPr is not None else OxmlElement('w:tblPr')

    # Remove all existing tblBorders
    for bb in tblPr.findall(qn('w:tblBorders')):
        tblPr.remove(bb)

    borders = OxmlElement('w:tblBorders')

    # top: 1.5pt
    top = OxmlElement('w:top')
    top.set(qn('w:val'), 'single')
    top.set(qn('w:sz'), '12')
    top.set(qn('w:space'), '0')
    top.set(qn('w:color'), '000000')
    borders.append(top)

    # bottom: 1.5pt
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '12')
    bottom.set(qn('w:space'), '0')
    bottom.set(qn('w:color'), '000000')
    borders.append(bottom)

    # left: none
    left = OxmlElement('w:left')
    left.set(qn('w:val'), 'none')
    left.set(qn('w:sz'), '0')
    left.set(qn('w:space'), '0')
    borders.append(left)

    # right: none
    right = OxmlElement('w:right')
    right.set(qn('w:val'), 'none')
    right.set(qn('w:sz'), '0')
    right.set(qn('w:space'), '0')
    borders.append(right)

    # insideH: none
    insideH = OxmlElement('w:insideH')
    insideH.set(qn('w:val'), 'none')
    insideH.set(qn('w:sz'), '0')
    insideH.set(qn('w:space'), '0')
    borders.append(insideH)

    # insideV: none
    insideV = OxmlElement('w:insideV')
    insideV.set(qn('w:val'), 'none')
    insideV.set(qn('w:sz'), '0')
    insideV.set(qn('w:space'), '0')
    borders.append(insideV)

    # Attach tblPr if missing
    if tbl.find(qn('w:tblPr')) is None:
        tbl.insert(0, tblPr)

    for old in tblPr.findall(qn('w:tblBorders')):
        tblPr.remove(old)
    tblPr.append(borders)

    # Header row bottom border: 0.75pt
    if len(table.rows) > 0:
        for cell in table.rows[0].cells:
            set_cell_border(cell,
                bottom={"sz": "6", "val": "single", "color": "000000", "space": "0"}
            )


def main():
    if len(sys.argv) != 3:
        print("Usage: python format_three_line.py <input.docx> <output.docx>")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    doc = Document(input_path)

    for table in doc.tables:
        apply_three_line_table(table)

    doc.save(output_path)
    print(f"Done: {output_path}")


if __name__ == "__main__":
    main()

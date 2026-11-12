#!/usr/bin/env python3
"""Export this project's thesis Markdown to a school-formatted DOCX.

The script intentionally uses only Python stdlib plus Pandoc.  Pandoc handles
Markdown, images, tables, and OMML math conversion; this script then patches the
OOXML package for the fragile thesis-specific formatting rules.
"""

from __future__ import annotations

import argparse
import copy
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
}
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"

for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)


BODY_FONT = "SimSun"
HEADING_FONT = "SimHei"
LATIN_FONT = "Times New Roman"
CODE_FONT = LATIN_FONT

HP_BODY = "24"  # 12 pt, Chinese xiao si
HP_CAPTION = "21"  # 10.5 pt, Chinese wu hao
HP_H1 = "32"  # 16 pt
HP_H2 = "28"  # 14 pt
TABLE_HEADER_ROW_HEIGHT = "330"  # 16.5 pt, compact but allows wrap growth
REFERENCE_ABSTRACT_NUM_ID = "9898"
REFERENCE_NUM_ID = "9898"

FIGURE_CAPTION_RE = re.compile(r"^图\s*\d+[-－]\d+(?:\s|$)")
TABLE_CAPTION_RE = re.compile(r"^表\s*\d+[-－]\d+(?:\s|$)")
IMAGE_LINE_RE = re.compile(r"^\s*!\[[^\]]*]\([^)]+\)\s*$")
IMAGE_LINK_RE = re.compile(r"!\[([^\]]*)]\(([^)]+)\)")
DISPLAY_MATH_DELIMITER_RE = re.compile(r"^\s*\$\$\s*$")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
TAG_RE = re.compile(r"\\tag\{([^}]+)\}")
EQ_MARK_RE = re.compile(r"^@@EQNO:([^@]+)@@$")
REFERENCE_HEADING_RE = re.compile(r"^#{1,6}\s*参考文献\s*$")
REFERENCE_ENTRY_RE = re.compile(r"^(?:[-*+]\s*)?\[(\d+)]\s*(.+?)\s*$")
TITLE_SPACING_TEXTS = {"摘要", "摘 要", "ABSTRACT", "目录", "目 录", "参考文献"}
NORMALIZED_TITLE_SPACING_TEXTS = {re.sub(r"\s+", "", x).upper() for x in TITLE_SPACING_TEXTS}


def qn(name: str) -> str:
    prefix, tag = name.split(":")
    return f"{{{NS[prefix]}}}{tag}"


BODY_ALLOWED_CHILDREN = {qn("w:p"), qn("w:tbl")}


def wa(name: str, value: str) -> tuple[str, str]:
    return qn(f"w:{name}"), value


def elem(name: str, attrs: dict[str, str] | None = None, text: str | None = None) -> ET.Element:
    e = ET.Element(qn(name))
    if attrs:
        for key, value in attrs.items():
            e.set(qn(f"w:{key}"), value)
    if text is not None:
        e.text = text
    return e


def get_or_add(parent: ET.Element, tag: str, first: bool = False) -> ET.Element:
    child = parent.find(qn(tag))
    if child is not None:
        return child
    child = elem(tag)
    if first:
        parent.insert(0, child)
    else:
        parent.append(child)
    return child


def insert_after(parent: ET.Element, anchor_tag: str, child: ET.Element) -> ET.Element:
    for i, existing in enumerate(list(parent)):
        if existing.tag == qn(anchor_tag):
            parent.insert(i + 1, child)
            return child
    parent.insert(0, child)
    return child


def paragraph_text(p: ET.Element) -> str:
    return "".join(t.text or "" for t in p.findall(".//w:t", NS))


def is_blank_p(node: ET.Element) -> bool:
    return node.tag == qn("w:p") and not paragraph_text(node).strip() and node.find(".//w:drawing", NS) is None


def has_drawing(p: ET.Element) -> bool:
    return p.find(".//w:drawing", NS) is not None


def has_math(p: ET.Element) -> bool:
    return p.find(".//m:oMath", NS) is not None or p.find(".//m:oMathPara", NS) is not None


def has_display_math(p: ET.Element) -> bool:
    return p.find("./m:oMathPara", NS) is not None


def get_ppr(p: ET.Element) -> ET.Element:
    return get_or_add(p, "w:pPr", first=True)


def get_rpr(r: ET.Element) -> ET.Element:
    return get_or_add(r, "w:rPr", first=True)


def remove_children(parent: ET.Element, tags: set[str]) -> None:
    for child in list(parent):
        if child.tag in tags:
            parent.remove(child)


def reorder_children(parent: ET.Element, ordered_tags: list[str]) -> None:
    order = {qn(tag): idx for idx, tag in enumerate(ordered_tags)}
    children = list(enumerate(list(parent)))
    children.sort(key=lambda item: (order.get(item[1].tag, len(ordered_tags)), item[0]))
    parent[:] = [child for _, child in children]


def set_jc(p: ET.Element, val: str) -> None:
    ppr = get_ppr(p)
    jc = get_or_add(ppr, "w:jc")
    jc.set(*wa("val", val))


def set_spacing(p: ET.Element, before: str = "0", after: str = "0", line: str = "300") -> None:
    spacing = get_or_add(get_ppr(p), "w:spacing")
    spacing.set(*wa("before", before))
    spacing.set(*wa("after", after))
    spacing.set(*wa("line", line))
    spacing.set(*wa("lineRule", "auto"))


def set_indent(p: ET.Element, first_line: str | None) -> None:
    ppr = get_ppr(p)
    ind = ppr.find(qn("w:ind"))
    if first_line is None:
        if ind is None:
            return
        for key in ("firstLine", "hanging"):
            ind.attrib.pop(qn(f"w:{key}"), None)
        if not ind.attrib:
            ppr.remove(ind)
        return
    if ind is None:
        ind = elem("w:ind")
        ppr.append(ind)
    for key in ("firstLine", "hanging"):
        ind.attrib.pop(qn(f"w:{key}"), None)
    ind.set(*wa("firstLine", first_line))


def set_left_indent(p: ET.Element, left: str | None) -> None:
    ppr = get_ppr(p)
    ind = ppr.find(qn("w:ind"))
    if left is None:
        if ind is None:
            return
        ind.attrib.pop(qn("w:left"), None)
        if not ind.attrib:
            ppr.remove(ind)
    else:
        if ind is None:
            ind = elem("w:ind")
            ppr.append(ind)
        ind.set(*wa("left", left))


def set_hanging_indent(p: ET.Element, left: str, hanging: str) -> None:
    ind = get_or_add(get_ppr(p), "w:ind")
    ind.attrib.pop(qn("w:firstLine"), None)
    ind.set(*wa("left", left))
    ind.set(*wa("hanging", hanging))


def clear_numbering(p: ET.Element) -> None:
    ppr = get_ppr(p)
    for num_pr in ppr.findall("./w:numPr", NS):
        ppr.remove(num_pr)


def set_numbering(p: ET.Element, num_id: str, level: str = "0") -> None:
    clear_numbering(p)
    ppr = get_ppr(p)
    num_pr = elem("w:numPr")
    ilvl = elem("w:ilvl")
    ilvl.set(*wa("val", level))
    num = elem("w:numId")
    num.set(*wa("val", num_id))
    num_pr.append(ilvl)
    num_pr.append(num)
    ppr.append(num_pr)


def set_tab_stop(p: ET.Element, pos: str) -> None:
    ppr = get_ppr(p)
    tabs = get_or_add(ppr, "w:tabs")
    tabs.clear()
    tab = elem("w:tab")
    tab.set(*wa("val", "left"))
    tab.set(*wa("pos", pos))
    tabs.append(tab)


def set_style(p: ET.Element, style_id: str) -> None:
    ppr = get_ppr(p)
    pstyle = get_or_add(ppr, "w:pStyle", first=True)
    pstyle.set(*wa("val", style_id))


def add_page_break_before(p: ET.Element) -> None:
    get_or_add(get_ppr(p), "w:pageBreakBefore")


def set_keep_next(p: ET.Element) -> None:
    get_or_add(get_ppr(p), "w:keepNext")


def set_run_font(
    r: ET.Element,
    east_asia: str = BODY_FONT,
    ascii_font: str = LATIN_FONT,
    size_hp: str = HP_BODY,
    bold: bool | None = None,
) -> None:
    if r.find(".//w:drawing", NS) is not None:
        return
    rpr = get_rpr(r)
    rfonts = get_or_add(rpr, "w:rFonts", first=True)
    for attr in ("ascii", "hAnsi", "cs"):
        rfonts.set(qn(f"w:{attr}"), ascii_font)
    rfonts.set(qn("w:eastAsia"), east_asia)
    sz = get_or_add(rpr, "w:sz")
    sz.set(*wa("val", size_hp))
    szcs = get_or_add(rpr, "w:szCs")
    szcs.set(*wa("val", size_hp))
    if bold is not None:
        for tag in ("w:b", "w:bCs"):
            existing = rpr.find(qn(tag))
            if bold:
                if existing is None:
                    rpr.append(elem(tag))
            elif existing is not None:
                rpr.remove(existing)


def set_paragraph_font(
    p: ET.Element,
    east_asia: str = BODY_FONT,
    ascii_font: str = LATIN_FONT,
    size_hp: str = HP_BODY,
    bold: bool | None = None,
) -> None:
    for r in p.findall("./w:r", NS):
        set_run_font(r, east_asia=east_asia, ascii_font=ascii_font, size_hp=size_hp, bold=bold)


PPR_ORDER = [
    "w:pStyle",
    "w:keepNext",
    "w:keepLines",
    "w:pageBreakBefore",
    "w:framePr",
    "w:widowControl",
    "w:numPr",
    "w:suppressLineNumbers",
    "w:pBdr",
    "w:shd",
    "w:tabs",
    "w:suppressAutoHyphens",
    "w:kinsoku",
    "w:wordWrap",
    "w:overflowPunct",
    "w:topLinePunct",
    "w:autoSpaceDE",
    "w:autoSpaceDN",
    "w:bidi",
    "w:adjustRightInd",
    "w:snapToGrid",
    "w:spacing",
    "w:ind",
    "w:jc",
    "w:textDirection",
    "w:textAlignment",
    "w:contextualSpacing",
    "w:mirrorIndents",
    "w:suppressOverlap",
]

TBLPR_ORDER = [
    "w:tblStyle",
    "w:tblpPr",
    "w:tblOverlap",
    "w:bidiVisual",
    "w:tblStyleRowBandSize",
    "w:tblStyleColBandSize",
    "w:tblW",
    "w:jc",
    "w:tblCellSpacing",
    "w:tblInd",
    "w:tblBorders",
    "w:shd",
    "w:tblLayout",
    "w:tblCellMar",
    "w:tblLook",
]

TRPR_ORDER = [
    "w:cantSplit",
    "w:trHeight",
    "w:tblHeader",
]

SECTPR_ORDER = [
    "w:headerReference",
    "w:footerReference",
    "w:footnotePr",
    "w:endnotePr",
    "w:type",
    "w:pgSz",
    "w:pgMar",
    "w:paperSrc",
    "w:pgBorders",
    "w:lnNumType",
    "w:pgNumType",
    "w:cols",
    "w:formProt",
    "w:vAlign",
    "w:noEndnote",
    "w:titlePg",
    "w:textDirection",
    "w:bidi",
    "w:docGrid",
    "w:printerSettings",
]


def normalize_ppr_order(p: ET.Element) -> None:
    ppr = p.find("./w:pPr", NS)
    if ppr is not None:
        reorder_children(ppr, PPR_ORDER)


def normalize_tblpr_order(tbl: ET.Element) -> None:
    tbl_pr = tbl.find("./w:tblPr", NS)
    if tbl_pr is not None:
        reorder_children(tbl_pr, TBLPR_ORDER)


def normalize_trpr_order(tr: ET.Element) -> None:
    tr_pr = tr.find("./w:trPr", NS)
    if tr_pr is not None:
        reorder_children(tr_pr, TRPR_ORDER)


def normalize_sectpr_order(body: ET.Element) -> None:
    sect_pr = body.find("./w:sectPr", NS)
    if sect_pr is not None:
        reorder_children(sect_pr, SECTPR_ORDER)


def make_text_run(text: str, east_asia: str, ascii_font: str, size_hp: str, bold: bool = False) -> ET.Element:
    r = elem("w:r")
    set_run_font(r, east_asia=east_asia, ascii_font=ascii_font, size_hp=size_hp, bold=bold)
    t = elem("w:t", text=text)
    if text.startswith(" ") or text.endswith(" "):
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    r.append(t)
    return r


def make_tab_run(east_asia: str, ascii_font: str, size_hp: str) -> ET.Element:
    r = elem("w:r")
    set_run_font(r, east_asia=east_asia, ascii_font=ascii_font, size_hp=size_hp, bold=False)
    r.append(elem("w:tab"))
    return r


def make_blank_p() -> ET.Element:
    p = elem("w:p")
    ppr = get_ppr(p)
    spacing = get_or_add(ppr, "w:spacing")
    spacing.set(*wa("before", "0"))
    spacing.set(*wa("after", "0"))
    spacing.set(*wa("line", "300"))
    spacing.set(*wa("lineRule", "auto"))
    p.append(make_text_run("", BODY_FONT, LATIN_FONT, HP_BODY))
    return p


def normalized_title_text(text: str) -> str:
    return re.sub(r"\s+", "", text).upper()


def needs_title_blank_lines(style: str | None, text: str) -> bool:
    if style == "Heading1":
        return True
    normalized = normalized_title_text(text)
    return normalized in NORMALIZED_TITLE_SPACING_TEXTS


def make_text_p(text: str, style_id: str = "BodyText") -> ET.Element:
    p = elem("w:p")
    set_style(p, style_id)
    p.append(make_text_run(text, BODY_FONT, LATIN_FONT, HP_BODY))
    return p


def normalize_reference_markdown(lines: list[str]) -> list[str]:
    heading_idx = None
    for idx, line in enumerate(lines):
        if REFERENCE_HEADING_RE.match(line.strip()):
            heading_idx = idx
            break
    if heading_idx is None:
        return lines

    entries: list[tuple[int, str]] = []
    pending_num: int | None = None
    pending_text: list[str] = []

    def flush_pending() -> None:
        nonlocal pending_num, pending_text
        if pending_num is not None:
            text = " ".join(part.strip() for part in pending_text if part.strip()).strip()
            entries.append((pending_num, f"[{pending_num}] {text}".rstrip()))
        pending_num = None
        pending_text = []

    for line in lines[heading_idx + 1:]:
        stripped = line.strip()
        if not stripped:
            continue
        match = REFERENCE_ENTRY_RE.match(stripped)
        if match:
            flush_pending()
            pending_num = int(match.group(1))
            pending_text = [match.group(2)]
            continue
        if pending_num is not None and not stripped.startswith("#"):
            pending_text.append(stripped)

    flush_pending()
    if not entries:
        return lines

    entries.sort(key=lambda item: item[0])
    normalized = lines[:heading_idx + 1] + [""]
    for _, text in entries:
        normalized.extend([text, ""])
    return normalized


def preprocess_markdown(src: Path, dst: Path, image_staging_dir: Path | None = None) -> None:
    lines = normalize_reference_markdown(src.read_text(encoding="utf-8-sig").splitlines())
    out: list[str] = []
    in_math = False
    math_lines: list[str] = []
    eq_no: str | None = None
    skip_next_figure_caption = False

    def append_blank_if_needed() -> None:
        if out and out[-1].strip():
            out.append("")

    for line in lines:
        stripped = line.strip()
        if skip_next_figure_caption:
            if not stripped:
                out.append(line)
                continue
            if FIGURE_CAPTION_RE.match(stripped):
                skip_next_figure_caption = False
                continue
            skip_next_figure_caption = False

        if stripped == "$$":
            if not in_math:
                append_blank_if_needed()
                out.append("$$")
                in_math = True
                math_lines = []
                eq_no = None
            else:
                formula_text = "\n".join(x for x in math_lines if x.strip()).strip()
                if formula_text:
                    out.extend(formula_text.splitlines())
                out.append("$$")
                if eq_no:
                    out.append("")
                    out.append(f"@@EQNO:{eq_no}@@")
                out.append("")
                in_math = False
            continue

        if in_math:
            match = TAG_RE.search(line)
            if match:
                eq_no = match.group(1).strip()
                line = TAG_RE.sub("", line).rstrip()
            math_lines.append(line)
            continue

        if IMAGE_LINE_RE.match(line):
            append_blank_if_needed()
            if image_staging_dir is None:
                out.append(normalize_markdown_image_targets(line))
            else:
                def replace_image(match: re.Match[str]) -> str:
                    raw_target = match.group(2)
                    target = _clean_markdown_image_target(raw_target)
                    if not target or _is_remote_or_uri_target(target):
                        return match.group(0)
                    staged = _stage_local_image_for_pandoc(target, src, image_staging_dir)
                    return f"![{match.group(1)}](<{staged}>)"

                out.append(IMAGE_LINK_RE.sub(replace_image, line))
            out.append("")
            skip_next_figure_caption = True
            continue

        if FIGURE_CAPTION_RE.match(stripped) or TABLE_CAPTION_RE.match(stripped):
            append_blank_if_needed()
            out.append(stripped)
            out.append("")
            continue

        if image_staging_dir is None:
            out.append(normalize_markdown_image_targets(line))
        else:
            def replace_image(match: re.Match[str]) -> str:
                raw_target = match.group(2)
                target = _clean_markdown_image_target(raw_target)
                if not target or _is_remote_or_uri_target(target):
                    return match.group(0)
                staged = _stage_local_image_for_pandoc(target, src, image_staging_dir)
                return f"![{match.group(1)}](<{staged}>)"

            out.append(IMAGE_LINK_RE.sub(replace_image, line))

    dst.write_text("\n".join(out).strip() + "\n", encoding="utf-8")


def find_pandoc(explicit: str | None) -> str:
    candidates = [
        explicit,
        os.environ.get("PANDOC"),
        r"C:\Users\43080\AppData\Local\Pandoc\pandoc.exe",
        shutil.which("pandoc"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise FileNotFoundError("Pandoc not found. Install Pandoc or pass --pandoc.")


def _clean_markdown_image_target(target: str) -> str:
    target = target.strip()
    if not target:
        return ""
    if target.startswith("<"):
        end = target.find(">")
        if end > 0:
            return target[1:end].strip()
    if target.startswith('"') or target.startswith("'"):
        quote = target[0]
        end = target.find(quote, 1)
        if end > 0:
            return target[1:end].strip()
    for marker in (' "', " '", " {"):
        if marker in target:
            target = target.split(marker, 1)[0].strip()
    return target


def _is_windows_drive_path(target: str) -> bool:
    return re.match(r"^[a-zA-Z]:[\\/]", target) is not None


def _is_remote_or_uri_target(target: str) -> bool:
    return re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) is not None and not _is_windows_drive_path(target)


def _is_local_absolute_image_target(target: str) -> bool:
    return _is_windows_drive_path(target) or Path(target).is_absolute()


def _normalize_absolute_image_target(target: str) -> str:
    path = Path(target)
    try:
        path = path.resolve(strict=False)
    except OSError:
        pass
    return path.as_posix()


def _sniff_local_image_suffix(path: Path) -> str | None:
    try:
        with path.open("rb") as f:
            head = f.read(12)
    except OSError:
        return None
    if head.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if head[:6] in {b"GIF87a", b"GIF89a"}:
        return ".gif"
    if head.startswith(b"BM"):
        return ".bmp"
    if head[:4] in {b"II*\x00", b"MM\x00*"}:
        return ".tif"
    return None


def _stage_local_image_for_pandoc(target: str, src: Path, staging_dir: Path) -> str:
    image_path = Path(target)
    if not image_path.is_absolute():
        image_path = src.parent / image_path
    if not image_path.exists():
        return target
    actual_suffix = _sniff_local_image_suffix(image_path)
    if not actual_suffix or image_path.suffix.lower() == actual_suffix:
        return _normalize_absolute_image_target(str(image_path))
    staging_dir.mkdir(parents=True, exist_ok=True)
    staged_path = staging_dir / f"{image_path.stem}{actual_suffix}"
    if not staged_path.exists():
        shutil.copy2(image_path, staged_path)
    return _normalize_absolute_image_target(str(staged_path))


def normalize_markdown_image_targets(line: str) -> str:
    def replace(match: re.Match[str]) -> str:
        raw_target = match.group(2)
        target = _clean_markdown_image_target(raw_target)
        if not target or _is_remote_or_uri_target(target) or not _is_local_absolute_image_target(target):
            return match.group(0)
        normalized = _normalize_absolute_image_target(target)
        return f"![{match.group(1)}](<{normalized}>)"

    return IMAGE_LINK_RE.sub(replace, line)


def collect_image_resource_dirs(src: Path) -> list[Path]:
    dirs: list[Path] = []

    def add(path: Path) -> None:
        resolved = path.resolve()
        if resolved not in dirs and resolved.exists() and resolved.is_dir():
            dirs.append(resolved)

    add(src.parent)
    try:
        for child in src.parent.iterdir():
            if child.is_dir():
                add(child)
    except OSError:
        pass
    if src.parent.parent.exists():
        add(src.parent.parent)

    try:
        text = src.read_text(encoding="utf-8-sig")
    except OSError:
        return dirs
    for match in IMAGE_LINK_RE.finditer(text):
        target = _clean_markdown_image_target(match.group(2))
        if not target or _is_remote_or_uri_target(target):
            continue
        image_path = Path(target)
        if not image_path.is_absolute():
            image_path = src.parent / image_path
        add(image_path.parent)
    return dirs


def find_missing_local_images(src: Path) -> list[Path]:
    try:
        text = src.read_text(encoding="utf-8-sig")
    except OSError:
        return []
    missing: list[Path] = []
    for match in IMAGE_LINK_RE.finditer(text):
        target = _clean_markdown_image_target(match.group(2))
        if not target or _is_remote_or_uri_target(target):
            continue
        image_path = Path(target)
        if not image_path.is_absolute():
            image_path = src.parent / image_path
        if not image_path.exists():
            missing.append(image_path)
    return missing


def _markdown_table_cell_count(line: str) -> int:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return 0
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return max(0, len(stripped.split("|")) - 1)


def collect_markdown_warnings(src: Path) -> list[str]:
    try:
        text = src.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise
    except OSError:
        return []

    warnings: list[str] = []
    missing_images = find_missing_local_images(src)
    if missing_images:
        warnings.append("检测到 Markdown 中存在无法访问的本地图片路径，软件会继续导出，缺失图片可能只显示为说明文字")
        for image_path in missing_images[:10]:
            warnings.append(f"缺失图片: {image_path}")
        if len(missing_images) > 10:
            warnings.append(f"还有 {len(missing_images) - 10} 个缺失图片未列出")

    for match in IMAGE_LINK_RE.finditer(text):
        alt = match.group(1).strip()
        target = _clean_markdown_image_target(match.group(2))
        if not alt:
            warnings.append(f"图片缺少 alt 文本，导出 Word 时不会生成规范图题: {target or '未写路径'}")
        if _is_remote_or_uri_target(target):
            warnings.append(f"检测到网络图片地址，离线或网络受限时可能无法插入 Word: {target}")

    lines = text.splitlines()
    delimiter_count = sum(1 for line in lines if DISPLAY_MATH_DELIMITER_RE.match(line))
    if delimiter_count % 2 == 1:
        warnings.append("检测到行间公式 `$$` 数量为奇数，可能存在未闭合公式块，软件会继续尝试导出")

    in_math = False
    math_start_line = 0
    math_buffer: list[str] = []
    for line_no, line in enumerate(lines, start=1):
        if DISPLAY_MATH_DELIMITER_RE.match(line):
            if in_math:
                formula = "\n".join(math_buffer)
                if formula.count("{") != formula.count("}"):
                    warnings.append(f"第 {math_start_line} 行附近公式花括号数量不匹配，公式可能按原始 TeX 文本导出")
                in_math = False
                math_buffer = []
            else:
                in_math = True
                math_start_line = line_no
                math_buffer = []
            continue
        if in_math:
            math_buffer.append(line)
        if "\\tag{" in line and not in_math:
            warnings.append(f"第 {line_no} 行检测到 `\\tag{{}}` 不在 `$$` 行间公式块内，公式编号可能无法右对齐")

    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip().lower()
        if re.search(r"<(div|span|table|tr|td|p|section|figure)(\s|>|$)", stripped) and not re.search(
            r"</(div|span|table|tr|td|p|section|figure)>", stripped
        ):
            warnings.append(f"第 {line_no} 行可能存在未闭合 HTML 标签，Pandoc 可能会自动补全但排版可能异常")
            break

    for idx, line in enumerate(lines):
        if not TABLE_SEPARATOR_RE.match(line):
            continue
        if idx == 0:
            continue
        expected = _markdown_table_cell_count(lines[idx - 1])
        if expected <= 0:
            continue
        for row_no in range(idx + 2, len(lines) + 1):
            row = lines[row_no - 1]
            if not row.strip() or not row.strip().startswith("|"):
                break
            actual = _markdown_table_cell_count(row)
            if actual and actual != expected:
                warnings.append(f"第 {row_no} 行表格列数与表头不一致，表格可能排版异常")
                break

    return warnings


def run_pandoc(md_path: Path, out_path: Path, reference: Path, resource_path: str, pandoc: str) -> None:
    cmd = [
        pandoc,
        str(md_path),
        "--from",
        "markdown+pipe_tables+tex_math_dollars-subscript",
        "--to",
        "docx",
        f"--reference-doc={reference}",
        f"--resource-path={resource_path}",
        "--standalone",
        f"--output={out_path}",
    ]
    proc = subprocess.run(
        cmd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.stderr.strip():
        print(proc.stderr.strip())
    if proc.returncode != 0:
        details = proc.stderr.strip() or proc.stdout.strip() or "Pandoc did not provide an error message."
        raise RuntimeError(f"Pandoc failed with exit code {proc.returncode}:\n{details}")


def split_image_caption(p: ET.Element) -> tuple[ET.Element, ET.Element] | None:
    text = paragraph_text(p).strip()
    if not has_drawing(p) or not FIGURE_CAPTION_RE.match(text):
        return None
    image_p = copy.deepcopy(p)
    for child in list(image_p):
        if child.tag == qn("w:pPr"):
            continue
        if child.find(".//w:drawing", NS) is None:
            image_p.remove(child)
    caption_p = make_text_p(text, "Caption")
    return image_p, caption_p


def format_image_p(p: ET.Element) -> None:
    set_style(p, "BodyText")
    set_jc(p, "center")
    set_indent(p, None)
    set_spacing(p, "0", "0", "300")
    normalize_ppr_order(p)


def format_figure_caption(p: ET.Element) -> None:
    set_style(p, "Caption")
    set_jc(p, "center")
    set_indent(p, None)
    set_spacing(p, "0", "0", "300")
    set_paragraph_font(p, BODY_FONT, LATIN_FONT, HP_CAPTION, bold=False)
    normalize_ppr_order(p)


def format_table_caption(p: ET.Element) -> None:
    set_style(p, "TableCaption")
    set_jc(p, "center")
    set_indent(p, None)
    set_spacing(p, "0", "0", "300")
    set_paragraph_font(p, HEADING_FONT, LATIN_FONT, HP_CAPTION, bold=False)
    normalize_ppr_order(p)


def format_body_p(p: ET.Element) -> None:
    text = paragraph_text(p).strip()
    style = get_style_val(p)
    if style == "Heading1":
        set_style(p, "Heading1")
        set_jc(p, "center")
        set_indent(p, None)
        set_spacing(p, "0", "0", "300")
        set_keep_next(p)
        set_paragraph_font(p, HEADING_FONT, LATIN_FONT, HP_H1, bold=False)
    elif style == "Heading2":
        set_jc(p, "left")
        set_indent(p, None)
        set_spacing(p, "0", "0", "300")
        set_keep_next(p)
        set_paragraph_font(p, HEADING_FONT, LATIN_FONT, HP_H2, bold=False)
    elif style == "Heading3":
        set_jc(p, "left")
        set_indent(p, None)
        set_spacing(p, "0", "0", "300")
        set_keep_next(p)
        set_paragraph_font(p, HEADING_FONT, LATIN_FONT, HP_BODY, bold=False)
    elif style in {"SourceCode", "Code"}:
        set_jc(p, "left")
        set_indent(p, None)
        set_left_indent(p, "480")
        set_spacing(p, "0", "0", "300")
        set_paragraph_font(p, BODY_FONT, CODE_FONT, HP_BODY, bold=False)
    elif text:
        if style not in {"Caption", "TableCaption"}:
            set_style(p, "BodyText")
        set_jc(p, "both")
        set_indent(p, "480")
        set_left_indent(p, None)
        set_spacing(p, "0", "0", "300")
        set_paragraph_font(p, BODY_FONT, LATIN_FONT, HP_BODY, bold=False)
    normalize_ppr_order(p)


def format_reference_p(p: ET.Element) -> None:
    text = paragraph_text(p).strip()
    match = REFERENCE_ENTRY_RE.match(text)
    if match:
        ppr = get_ppr(p)
        for child in list(p):
            if child is not ppr:
                p.remove(child)
        set_numbering(p, REFERENCE_NUM_ID)
        p.append(make_text_run(match.group(2).strip(), BODY_FONT, LATIN_FONT, HP_BODY))
    else:
        clear_numbering(p)
    set_style(p, "BodyText")
    set_jc(p, "left")
    set_indent(p, None)
    set_left_indent(p, None)
    set_spacing(p, "0", "0", "240")
    set_paragraph_font(p, BODY_FONT, LATIN_FONT, HP_BODY, bold=False)
    normalize_ppr_order(p)


def format_title_p(p: ET.Element) -> None:
    set_jc(p, "center")
    set_indent(p, None)
    set_spacing(p, "0", "0", "300")
    set_keep_next(p)
    set_paragraph_font(p, HEADING_FONT, LATIN_FONT, HP_H1, bold=False)
    normalize_ppr_order(p)


def get_style_val(p: ET.Element) -> str | None:
    style = p.find("./w:pPr/w:pStyle", NS)
    if style is None:
        return None
    return style.get(qn("w:val"))


def remove_table_borders(tbl_pr: ET.Element) -> None:
    borders = get_or_add(tbl_pr, "w:tblBorders")
    for name in ("top", "left", "bottom", "right", "insideH", "insideV"):
        b = get_or_add(borders, f"w:{name}")
        b.set(*wa("val", "nil"))


def set_border(parent: ET.Element, name: str, value: str, size: str = "0") -> None:
    border = get_or_add(parent, f"w:{name}")
    border.set(*wa("val", value))
    border.set(*wa("color", "000000"))
    border.set(*wa("sz", size))
    border.set(*wa("space", "0"))


def set_cell_borders(tc: ET.Element, *, top: str | None = None, bottom: str | None = None) -> None:
    tc_pr = get_or_add(tc, "w:tcPr", first=True)
    borders = get_or_add(tc_pr, "w:tcBorders")
    borders.clear()
    for name in ("top", "left", "bottom", "right"):
        set_border(borders, name, "nil")
    if top:
        set_border(borders, "top", "single", top)
    if bottom:
        set_border(borders, "bottom", "single", bottom)
    v_align = get_or_add(tc_pr, "w:vAlign")
    v_align.set(*wa("val", "center"))


def format_three_line_table(tbl: ET.Element) -> None:
    tbl_pr = get_or_add(tbl, "w:tblPr", first=True)
    jc = get_or_add(tbl_pr, "w:jc")
    jc.set(*wa("val", "center"))
    remove_table_borders(tbl_pr)

    rows = tbl.findall("./w:tr", NS)
    if not rows:
        return

    last_idx = len(rows) - 1
    for row_idx, tr in enumerate(rows):
        tr_pr = tr.find("./w:trPr", NS)
        if tr_pr is not None:
            for height in tr_pr.findall("./w:trHeight", NS):
                tr_pr.remove(height)
        if row_idx == 0:
            set_row_height(tr, TABLE_HEADER_ROW_HEIGHT, "atLeast")

        for tc in tr.findall("./w:tc", NS):
            top = "10" if row_idx == 0 else None
            if row_idx == last_idx:
                bottom = "10"
            elif row_idx == 0:
                bottom = "6"
            else:
                bottom = None
            set_cell_borders(tc, top=top, bottom=bottom)
        normalize_trpr_order(tr)
    normalize_tblpr_order(tbl)


def set_row_height(tr: ET.Element, height: str, rule: str = "exact") -> None:
    tr_pr = get_or_add(tr, "w:trPr", first=True)
    tr_height = get_or_add(tr_pr, "w:trHeight")
    tr_height.set(*wa("val", height))
    tr_height.set(*wa("hRule", rule))


def make_tc(width: str) -> ET.Element:
    tc = elem("w:tc")
    tc_pr = get_or_add(tc, "w:tcPr")
    tc_w = get_or_add(tc_pr, "w:tcW")
    tc_w.set(*wa("w", width))
    tc_w.set(*wa("type", "dxa"))
    v_align = get_or_add(tc_pr, "w:vAlign")
    v_align.set(*wa("val", "center"))
    return tc


def make_formula_table(math_p: ET.Element, number: str) -> ET.Element:
    tbl = elem("w:tbl")
    tbl_pr = get_or_add(tbl, "w:tblPr")
    tbl_w = get_or_add(tbl_pr, "w:tblW")
    tbl_w.set(*wa("w", "9000"))
    tbl_w.set(*wa("type", "dxa"))
    layout = get_or_add(tbl_pr, "w:tblLayout")
    layout.set(*wa("type", "fixed"))
    remove_table_borders(tbl_pr)

    grid = get_or_add(tbl, "w:tblGrid")
    grid.append(elem("w:gridCol", {"w": "7800"}))
    grid.append(elem("w:gridCol", {"w": "1200"}))

    tr = elem("w:tr")
    left_tc = make_tc("7800")
    right_tc = make_tc("1200")

    left_p = elem("w:p")
    set_jc(left_p, "center")
    set_indent(left_p, None)
    set_spacing(left_p, "0", "0", "300")
    for child in [copy.deepcopy(x) for x in list(math_p) if x.tag != qn("w:pPr")]:
        for omath_para in child.findall(".//m:oMathPara", NS):
            pr = get_or_add(omath_para, "m:oMathParaPr", first=True)
            jc = get_or_add(pr, "m:jc")
            jc.set(qn("m:val"), "center")
        left_p.append(child)
    right_p = make_equation_number_p(number)
    left_tc.append(left_p)
    right_tc.append(right_p)
    tr.append(left_tc)
    tr.append(right_tc)
    tbl.append(tr)
    normalize_ppr_order(left_p)
    normalize_ppr_order(right_p)
    normalize_tblpr_order(tbl)
    normalize_trpr_order(tr)
    return tbl


def set_math_run_size(node: ET.Element) -> None:
    return


def make_equation_number_p(number: str) -> ET.Element:
    number_p = elem("w:p")
    set_style(number_p, "BodyText")
    set_jc(number_p, "right")
    set_indent(number_p, None)
    set_spacing(number_p, "0", "0", "300")
    number_p.append(make_text_run(f"({number})", BODY_FONT, LATIN_FONT, HP_BODY))
    normalize_ppr_order(number_p)
    return number_p


def format_table_runs(tbl: ET.Element) -> None:
    rows = tbl.findall("./w:tr", NS)
    if len(rows) == 1:
        cells = rows[0].findall("./w:tc", NS)
        if len(cells) == 2:
            right_text = ""
            try:
                right_text = paragraph_text(cells[1]).replace("\r", "").replace("\a", "").strip()
            except Exception:
                right_text = ""
            if re.fullmatch(r"\(\d+-\d+\)", right_text):
                return
    format_three_line_table(tbl)
    for p in tbl.findall(".//w:p", NS):
        set_jc(p, "center")
        set_indent(p, None)
        set_spacing(p, "0", "0", "300")
        set_paragraph_font(p, BODY_FONT, LATIN_FONT, HP_CAPTION, bold=False)
        normalize_ppr_order(p)


def set_section_page_numbers(body: ET.Element) -> None:
    sect_pr = body.find("./w:sectPr", NS)
    if sect_pr is None:
        sect_pr = elem("w:sectPr")
        body.append(sect_pr)
    pg_num = get_or_add(sect_pr, "w:pgNumType")
    pg_num.set(*wa("fmt", "decimal"))
    pg_num.set(*wa("start", "1"))
    normalize_sectpr_order(body)


def patch_document_xml(xml_bytes: bytes) -> tuple[bytes, dict[str, int]]:
    root = ET.fromstring(xml_bytes)
    body = root.find("w:body", NS)
    if body is None:
        raise RuntimeError("word/document.xml has no w:body")

    old_children = list(body)
    body.clear()
    new_children: list[ET.Element] = []
    section_props: ET.Element | None = None
    stats = {"figures": 0, "figure_captions": 0, "table_captions": 0, "equations": 0, "heading1": 0}
    in_references = False
    i = 0

    def append_blank_before() -> None:
        if new_children and not is_blank_p(new_children[-1]):
            new_children.append(make_blank_p())

    def trim_trailing_blanks() -> None:
        while new_children and is_blank_p(new_children[-1]):
            new_children.pop()

    def append_title_block(p: ET.Element, page_break_before: bool = False) -> None:
        trim_trailing_blanks()
        first_blank = make_blank_p()
        if page_break_before:
            add_page_break_before(first_blank)
        new_children.append(first_blank)
        new_children.append(make_blank_p())
        new_children.append(p)
        new_children.append(make_blank_p())

    while i < len(old_children):
        node = old_children[i]

        if node.tag == qn("w:sectPr"):
            section_props = node
            i += 1
            continue

        if node.tag not in BODY_ALLOWED_CHILDREN:
            i += 1
            continue

        if node.tag == qn("w:p"):
            split = split_image_caption(node)
            if split:
                old_children[i:i + 1] = [split[0], split[1]]
                node = old_children[i]
            if has_math(node):
                set_math_run_size(node)

            text = paragraph_text(node).strip()
            style = get_style_val(node)
            marker = EQ_MARK_RE.match(text)
            if marker:
                i += 1
                continue

            if has_display_math(node):
                next_text = paragraph_text(old_children[i + 1]).strip() if i + 1 < len(old_children) and old_children[i + 1].tag == qn("w:p") else ""
                next_marker = EQ_MARK_RE.match(next_text)
                if next_marker:
                    new_children.append(make_formula_table(node, next_marker.group(1)))
                    stats["equations"] += 1
                    i += 2
                    continue
                set_jc(node, "center")
                set_indent(node, None)
                set_left_indent(node, None)
                set_spacing(node, "0", "0", "300")
                new_children.append(node)
                i += 1
                continue

            if has_drawing(node):
                append_blank_before()
                format_image_p(node)
                new_children.append(node)
                stats["figures"] += 1
                i += 1
                continue

            if FIGURE_CAPTION_RE.match(text) and new_children and new_children[-1].tag == qn("w:p") and has_drawing(new_children[-1]):
                format_figure_caption(node)
                new_children.append(node)
                new_children.append(make_blank_p())
                stats["figure_captions"] += 1
                i += 1
                continue

            if TABLE_CAPTION_RE.match(text):
                append_blank_before()
                format_table_caption(node)
                new_children.append(node)
                stats["table_captions"] += 1
                if i + 1 < len(old_children) and old_children[i + 1].tag == qn("w:tbl"):
                    tbl = old_children[i + 1]
                    format_table_runs(tbl)
                    new_children.append(tbl)
                    new_children.append(make_blank_p())
                    i += 2
                    continue
                new_children.append(make_blank_p())
                i += 1
                continue

            if in_references and REFERENCE_ENTRY_RE.match(text):
                format_reference_p(node)
                new_children.append(node)
                i += 1
                continue

            if needs_title_blank_lines(style, text):
                if style == "Heading1":
                    format_body_p(node)
                else:
                    format_title_p(node)
                if style == "Heading1":
                    stats["heading1"] += 1
                append_title_block(node, page_break_before=(style == "Heading1"))
                in_references = normalized_title_text(text) == "参考文献"
                i += 1
                continue

            if in_references:
                format_reference_p(node)
                new_children.append(node)
                i += 1
                continue

            format_body_p(node)
            new_children.append(node)
            i += 1
            continue

        if node.tag == qn("w:tbl"):
            append_blank_before()
            format_table_runs(node)
            new_children.append(node)
            new_children.append(make_blank_p())
            i += 1
            continue

        new_children.append(node)
        i += 1

    if section_props is not None:
        new_children.append(section_props)

    for node in new_children:
        body.append(node)
    set_section_page_numbers(body)
    normalize_sectpr_order(body)

    return ET.tostring(root, encoding="utf-8", xml_declaration=True), stats


def set_style_prop(style: ET.Element, east_asia: str, ascii_font: str, size_hp: str, bold: bool | None = None) -> None:
    rpr = get_or_add(style, "w:rPr")
    rfonts = get_or_add(rpr, "w:rFonts", first=True)
    for attr in ("ascii", "hAnsi", "cs"):
        rfonts.set(qn(f"w:{attr}"), ascii_font)
    rfonts.set(qn("w:eastAsia"), east_asia)
    sz = get_or_add(rpr, "w:sz")
    sz.set(*wa("val", size_hp))
    szcs = get_or_add(rpr, "w:szCs")
    szcs.set(*wa("val", size_hp))
    if bold is not None:
        for tag in ("w:b", "w:bCs"):
            b = rpr.find(qn(tag))
            if bold and b is None:
                rpr.append(elem(tag))
            elif not bold and b is not None:
                rpr.remove(b)


def ensure_style(root: ET.Element, style_id: str, name: str, style_type: str = "paragraph") -> ET.Element:
    for style in root.findall("./w:style", NS):
        if style.get(qn("w:styleId")) == style_id:
            return style
    style = elem("w:style")
    style.set(*wa("type", style_type))
    style.set(*wa("styleId", style_id))
    style.append(elem("w:name", {"val": name}))
    root.append(style)
    return style


def patch_styles_xml(xml_bytes: bytes) -> bytes:
    root = ET.fromstring(xml_bytes)
    specs = {
        "Normal": (BODY_FONT, LATIN_FONT, HP_BODY, False),
        "BodyText": (BODY_FONT, LATIN_FONT, HP_BODY, False),
        "ReferenceText": (BODY_FONT, LATIN_FONT, HP_BODY, False),
        "FirstParagraph": (BODY_FONT, LATIN_FONT, HP_BODY, False),
        "Compact": (BODY_FONT, LATIN_FONT, HP_BODY, False),
        "Caption": (BODY_FONT, LATIN_FONT, HP_CAPTION, False),
        "ImageCaption": (BODY_FONT, LATIN_FONT, HP_CAPTION, False),
        "TableCaption": (HEADING_FONT, LATIN_FONT, HP_CAPTION, False),
        "Heading1": (HEADING_FONT, LATIN_FONT, HP_H1, False),
        "Heading2": (HEADING_FONT, LATIN_FONT, HP_H2, False),
        "Heading3": (HEADING_FONT, LATIN_FONT, HP_BODY, False),
        "SourceCode": (BODY_FONT, CODE_FONT, HP_BODY, False),
        "Code": (BODY_FONT, CODE_FONT, HP_BODY, False),
    }
    for style_id, (ea, ascii_font, size, bold) in specs.items():
        style = ensure_style(root, style_id, style_id)
        set_style_prop(style, ea, ascii_font, size, bold)
        if style_id == "Heading1":
            ppr = get_or_add(style, "w:pPr")
            jc = get_or_add(ppr, "w:jc")
            jc.set(*wa("val", "center"))
        elif style_id in {"Caption", "ImageCaption", "TableCaption"}:
            ppr = get_or_add(style, "w:pPr")
            jc = get_or_add(ppr, "w:jc")
            jc.set(*wa("val", "center"))
    return replace_font_names(ET.tostring(root, encoding="utf-8", xml_declaration=True))


def replace_font_names(xml_bytes: bytes) -> bytes:
    text = xml_bytes.decode("utf-8")
    for old in ("宋体", "仿宋", "SimSun-ExtB"):
        text = text.replace(old, BODY_FONT)
    for old in ("黑体",):
        text = text.replace(old, HEADING_FONT)
    return text.encode("utf-8")


def patch_header_xml(xml_bytes: bytes) -> bytes:
    text = xml_bytes.decode("utf-8")
    text = re.sub(r'\s+r:link="[^"]*"', "", text)
    return replace_font_names(text.encode("utf-8"))


def patch_header_rels(xml_bytes: bytes) -> bytes:
    ET.register_namespace("", REL_NS)
    root = ET.fromstring(xml_bytes)
    rel_tag = f"{{{REL_NS}}}Relationship"
    changed = False
    for rel in list(root.findall(rel_tag)):
        if rel.get("Type") == "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" and rel.get("TargetMode") == "External":
            root.remove(rel)
            changed = True
    if not changed:
        return xml_bytes
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def make_reference_numbering_root() -> ET.Element:
    root = ET.Element(qn("w:numbering"))
    return patch_numbering_root(root)


def patch_numbering_root(root: ET.Element) -> ET.Element:
    for child in list(root):
        if child.tag == qn("w:abstractNum") and child.get(qn("w:abstractNumId")) == REFERENCE_ABSTRACT_NUM_ID:
            root.remove(child)
        elif child.tag == qn("w:num") and child.get(qn("w:numId")) == REFERENCE_NUM_ID:
            root.remove(child)

    abstract = elem("w:abstractNum")
    abstract.set(*wa("abstractNumId", REFERENCE_ABSTRACT_NUM_ID))
    abstract.append(elem("w:nsid", {"val": "00A0A898"}))
    abstract.append(elem("w:multiLevelType", {"val": "singleLevel"}))
    lvl = elem("w:lvl")
    lvl.set(*wa("ilvl", "0"))
    lvl.append(elem("w:start", {"val": "1"}))
    lvl.append(elem("w:numFmt", {"val": "decimal"}))
    lvl.append(elem("w:lvlText", {"val": "[%1]"}))
    lvl.append(elem("w:suff", {"val": "space"}))
    lvl.append(elem("w:lvlJc", {"val": "left"}))
    ppr = elem("w:pPr")
    ind = elem("w:ind")
    ind.set(*wa("left", "0"))
    ind.set(*wa("hanging", "0"))
    ppr.append(ind)
    lvl.append(ppr)
    rpr = elem("w:rPr")
    rfonts = elem("w:rFonts")
    for attr in ("ascii", "hAnsi", "cs"):
        rfonts.set(qn(f"w:{attr}"), LATIN_FONT)
    rfonts.set(qn("w:eastAsia"), BODY_FONT)
    rpr.append(rfonts)
    rpr.append(elem("w:sz", {"val": HP_BODY}))
    rpr.append(elem("w:szCs", {"val": HP_BODY}))
    lvl.append(rpr)
    abstract.append(lvl)
    root.append(abstract)

    num = elem("w:num")
    num.set(*wa("numId", REFERENCE_NUM_ID))
    abstract_num_id = elem("w:abstractNumId")
    abstract_num_id.set(*wa("val", REFERENCE_ABSTRACT_NUM_ID))
    num.append(abstract_num_id)
    root.append(num)
    return root


def patch_numbering_xml(xml_bytes: bytes | None = None) -> bytes:
    if xml_bytes:
        root = ET.fromstring(xml_bytes)
        patch_numbering_root(root)
    else:
        root = make_reference_numbering_root()
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def ensure_numbering_relationship(xml_bytes: bytes) -> bytes:
    ET.register_namespace("", REL_NS)
    root = ET.fromstring(xml_bytes)
    relationship_tag = f"{{{REL_NS}}}Relationship"
    for rel in root.findall(relationship_tag):
        if rel.get("Type") == "http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering":
            return xml_bytes
    used_ids = {rel.get("Id", "") for rel in root.findall(relationship_tag)}
    next_idx = 1
    while f"rId{next_idx}" in used_ids:
        next_idx += 1
    rel = ET.Element(relationship_tag)
    rel.set("Id", f"rId{next_idx}")
    rel.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering")
    rel.set("Target", "numbering.xml")
    root.append(rel)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def ensure_numbering_content_type(xml_bytes: bytes) -> bytes:
    ET.register_namespace("", CONTENT_TYPES_NS)
    root = ET.fromstring(xml_bytes)
    override_tag = f"{{{CONTENT_TYPES_NS}}}Override"
    for override in root.findall(override_tag):
        if override.get("PartName") == "/word/numbering.xml":
            return xml_bytes
    override = ET.Element(override_tag)
    override.set("PartName", "/word/numbering.xml")
    override.set("ContentType", "application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml")
    root.append(override)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def run_word_postprocess(docx_path: Path, template_path: Path) -> Path:
    backend = os.environ.get("THESIS_WORD_BACKEND", "auto").lower()
    if backend in {"", "none", "off", "disabled"}:
        return docx_path
    if os.name == "nt" and backend == "powershell":
        return run_word_postprocess_powershell(docx_path, template_path)

    try:
        import pythoncom
        from win32com.client import DispatchEx
    except ImportError:
        return run_word_postprocess_powershell(docx_path, template_path)

    wd_header_footer_primary = 1
    wd_header_footer_first_page = 2
    wd_header_footer_even_pages = 3
    wd_page_number_style_arabic = 0
    wd_page_number_style_lowercase_roman = 2
    wd_format_xml_document = 16
    wd_align_paragraph_left = 0
    wd_align_paragraph_center = 1
    wd_align_paragraph_right = 2
    wd_line_space_single = 0
    wd_number_gallery = 2
    wd_list_apply_to_whole_list = 0
    wd_word10_list_behavior = 2

    pythoncom.CoInitialize()
    word = None
    doc = None
    template_doc = None
    save_copy_path = docx_path.with_name(docx_path.stem + ".__codex_save__.docx")
    try:
        word = DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        doc = word.Documents.Open(str(docx_path), False, False)
        template_doc = word.Documents.Open(str(template_path), False, True)

        for section in doc.Sections:
            for kind in (
                wd_header_footer_primary,
                wd_header_footer_first_page,
                wd_header_footer_even_pages,
            ):
                section.Headers.Item(kind).Range.FormattedText = (
                    template_doc.Sections.Item(1).Headers.Item(kind).Range.FormattedText
                )

        for idx in range(1, doc.OMaths.Count + 1):
            math_range = doc.OMaths.Item(idx).Range
            math_range.Font.Size = 14
            math_range.Font.Name = "Times New Roman"
            math_range.Font.NameFarEast = "SimSun"

        for table in doc.Tables:
            if table.Rows.Count == 1 and table.Columns.Count == 2:
                try:
                    right_text = str(table.Cell(1, 2).Range.Text).replace("\r", "").replace("\a", "")
                except Exception:
                    right_text = ""
                if re.fullmatch(r"\(\d+-\d+\)", right_text):
                    table.Cell(1, 1).Range.ParagraphFormat.Alignment = wd_align_paragraph_center
                    table.Cell(1, 2).Range.ParagraphFormat.Alignment = wd_align_paragraph_right
                    table.Cell(1, 2).Range.Font.Name = "Times New Roman"
                    table.Cell(1, 2).Range.Font.NameFarEast = "SimSun"
                    table.Cell(1, 2).Range.Font.Size = 12

        reference_ranges: list[tuple[int, int]] = []
        for para in doc.Paragraphs:
            style_name = ""
            try:
                style_name = str(para.Range.Style.NameLocal)
            except Exception:
                pass
            para_text = ""
            try:
                para_text = str(para.Range.Text).replace("\r", "").replace("\a", "").strip()
            except Exception:
                pass
            para.SpaceBefore = 0
            para.SpaceAfter = 0
            if re.match(r"^\[\d+\]", para_text):
                try:
                    para.Range.ListFormat.RemoveNumbers()
                except Exception:
                    pass
                marker = re.match(r"^\[\d+\]\s*", para_text)
                if marker:
                    marker_range = para.Range.Duplicate
                    marker_range.SetRange(para.Range.Start, para.Range.Start + len(marker.group(0)))
                    marker_range.Delete()
                para.Alignment = wd_align_paragraph_left
                para.LineSpacingRule = wd_line_space_single
                para.LeftIndent = 0
                para.FirstLineIndent = 0
                try:
                    para.TabStops.ClearAll()
                except Exception:
                    pass
                para.Range.Font.Name = "Times New Roman"
                para.Range.Font.NameFarEast = "SimSun"
                para.Range.Font.Size = 12
                para.Range.Font.Bold = 0
                reference_ranges.append((para.Range.Start, para.Range.End))
                continue
            if re.search(r"Source Code|Code", style_name):
                para.Range.Font.Name = "Times New Roman"
                para.Range.Font.NameFarEast = "SimSun"
                para.Range.Font.Size = 12
                para.Range.Font.Bold = 0
                for char_idx in range(1, para.Range.Characters.Count + 1):
                    char_font = para.Range.Characters.Item(char_idx).Font
                    char_font.Name = "Times New Roman"
                    char_font.NameFarEast = "SimSun"
                    char_font.Bold = 0
                para.LeftIndent = 24

        if reference_ranges:
            ref_start = min(start for start, _ in reference_ranges)
            ref_end = max(end for _, end in reference_ranges)
            ref_range = doc.Range(ref_start, ref_end)
            list_template = word.ListGalleries.Item(wd_number_gallery).ListTemplates.Item(1)
            level = list_template.ListLevels.Item(1)
            level.NumberFormat = "[%1]"
            level.NumberStyle = 0
            level.NumberPosition = 0
            level.Alignment = wd_align_paragraph_left
            level.TextPosition = 0
            level.TabPosition = 0
            level.TrailingCharacter = 1
            level.StartAt = 1
            ref_range.ListFormat.ApplyListTemplateWithLevel(
                list_template,
                False,
                wd_list_apply_to_whole_list,
                wd_word10_list_behavior,
                1,
            )
            for para in ref_range.Paragraphs:
                para.Alignment = wd_align_paragraph_left
                para.LineSpacingRule = wd_line_space_single
                para.SpaceBefore = 0
                para.SpaceAfter = 0
                para.LeftIndent = 0
                para.FirstLineIndent = 0
                try:
                    para.TabStops.ClearAll()
                except Exception:
                    pass
                para.Range.Font.Name = "Times New Roman"
                para.Range.Font.NameFarEast = "SimSun"
                para.Range.Font.Size = 12
                para.Range.Font.Bold = 0

        if doc.Sections.Count >= 2:
            try:
                footer = doc.Sections.Item(1).Footers.Item(wd_header_footer_primary).PageNumbers
            except Exception:
                footer = None
            if footer is not None:
                footer.RestartNumberingAtSection = True
                footer.StartingNumber = 1
                footer.NumberStyle = wd_page_number_style_lowercase_roman
            for section_idx in range(2, doc.Sections.Count + 1):
                try:
                    footer = doc.Sections.Item(section_idx).Footers.Item(wd_header_footer_primary).PageNumbers
                except Exception:
                    footer = None
                if footer is not None:
                    footer.RestartNumberingAtSection = True
                    footer.StartingNumber = 1
                    footer.NumberStyle = wd_page_number_style_arabic
        else:
            try:
                footer = doc.Sections.Item(1).Footers.Item(wd_header_footer_primary).PageNumbers
            except Exception:
                footer = None
            if footer is not None:
                footer.RestartNumberingAtSection = True
                footer.StartingNumber = 1
                footer.NumberStyle = wd_page_number_style_arabic

        if save_copy_path.exists():
            save_copy_path.unlink()
        doc.SaveAs2(str(save_copy_path), wd_format_xml_document)
        doc.Close(False)
        doc = None
        template_doc.Close(False)
        template_doc = None
        word.Quit()
        word = None
        processed_path = save_copy_path
        save_copy_path = None
        return processed_path
    finally:
        if template_doc is not None:
            try:
                template_doc.Close(False)
            except Exception:
                pass
        if doc is not None:
            try:
                doc.Close(False)
            except Exception:
                pass
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
        if save_copy_path is not None and save_copy_path.exists():
            try:
                save_copy_path.unlink()
            except Exception:
                pass
        pythoncom.CoUninitialize()


def replace_file_with_retry(src_path: Path, dst_path: Path, retries: int = 120, delay_s: float = 0.5) -> None:
    last_error: Exception | None = None
    for _ in range(retries):
        try:
            if dst_path.exists():
                dst_path.unlink()
            shutil.move(str(src_path), str(dst_path))
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(delay_s)
    if last_error is not None:
        raise last_error


def run_word_postprocess_powershell(docx_path: Path, template_path: Path) -> Path:
    script_path = Path(__file__).with_name("word_postprocess.ps1")
    if not script_path.exists():
        raise FileNotFoundError(script_path)
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-DocxPath",
        str(docx_path),
        "-TemplatePath",
        str(template_path),
    ]
    timeout_s = int(os.environ.get("WORD_POSTPROCESS_TIMEOUT", "300"))
    try:
        proc = subprocess.run(
            cmd,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_s,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(
            f"Word postprocess timed out after {timeout_s}s for {docx_path}. "
            "Check whether Word/WPS has locked the file or Word automation is blocked."
        ) from exc
    if proc.returncode != 0:
        details = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"Word postprocess failed with exit code {proc.returncode}:\n{details}")
    for line in (proc.stdout or "").splitlines():
        if line.startswith("POSTPROCESS_OUTPUT="):
            processed_path = Path(line.split("=", 1)[1].strip())
            if processed_path.exists():
                return processed_path
    return docx_path


def normalize_word_xml_fonts_in_place(docx_path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="thesis_docx_fonts_") as td:
        temp_docx = Path(td) / "normalized.docx"
        with zipfile.ZipFile(docx_path, "r") as zin, zipfile.ZipFile(temp_docx, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename.startswith("word/") and info.filename.endswith(".xml"):
                    data = replace_font_names(data)
                zout.writestr(info, data)
        replace_file_with_retry(temp_docx, docx_path)


def patch_docx_package(src_docx: Path, dst_docx: Path) -> dict[str, int]:
    with tempfile.TemporaryDirectory(prefix="thesis_docx_patch_") as td:
        temp_docx = Path(td) / "patched.docx"
        stats: dict[str, int] = {}
        has_numbering = False
        with zipfile.ZipFile(src_docx, "r") as zin, zipfile.ZipFile(temp_docx, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename == "word/document.xml":
                    data, stats = patch_document_xml(data)
                elif info.filename == "word/numbering.xml":
                    has_numbering = True
                    data = patch_numbering_xml(data)
                elif info.filename == "word/_rels/document.xml.rels":
                    data = ensure_numbering_relationship(data)
                elif info.filename.startswith("word/header") and info.filename.endswith(".xml"):
                    data = patch_header_xml(data)
                elif info.filename.startswith("word/_rels/header") and info.filename.endswith(".rels"):
                    data = patch_header_rels(data)
                elif info.filename == "[Content_Types].xml":
                    data = ensure_numbering_content_type(data)
                elif info.filename.startswith("word/") and info.filename.endswith(".xml"):
                    data = replace_font_names(data)
                zout.writestr(info, data)
            if not has_numbering:
                zout.writestr("word/numbering.xml", patch_numbering_xml())
        dst_docx.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(temp_docx), str(dst_docx))
        return stats


def inspect_docx(docx_path: Path) -> dict[str, int | bool]:
    with zipfile.ZipFile(docx_path, "r") as zf:
        document = zf.read("word/document.xml").decode("utf-8", errors="ignore")
        styles = zf.read("word/styles.xml").decode("utf-8", errors="ignore")
    return {
        "images": document.count("<w:drawing"),
        "tables": len(re.findall(r"<w:tbl(?:\s|>)", document)),
        "raw_tag": "\\tag{" in document,
        "eq_markers": "@@EQNO:" in document,
        "chinese_songti": "宋体" in document or "宋体" in styles,
        "sim_sun": "SimSun" in document or "SimSun" in styles,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    skill_root = Path(__file__).resolve().parents[1]
    default_reference = skill_root / "assets" / "reference.docx"
    parser = argparse.ArgumentParser(description="Export GraduationThesis Markdown to formatted DOCX.")
    parser.add_argument("--input", "-i", required=True, type=Path, help="Source thesis Markdown path.")
    parser.add_argument("--output", "-o", required=True, type=Path, help="Destination DOCX path.")
    parser.add_argument("--reference", type=Path, default=default_reference, help="Pandoc reference DOCX/DOTX.")
    parser.add_argument("--pandoc", default=None, help="Pandoc executable path.")
    parser.add_argument(
        "--resource-path",
        default=None,
        help="Pandoc resource path. Defaults to the Markdown folder and its project root.",
    )
    parser.add_argument("--keep-temp", action="store_true", help="Keep intermediate Markdown/DOCX for debugging.")
    parser.add_argument("--suppress-warnings", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    src = args.input.resolve()
    out = args.output.resolve()
    reference = args.reference.resolve()
    if not src.exists():
        raise FileNotFoundError(src)
    if not reference.exists():
        raise FileNotFoundError(reference)
    if not args.suppress_warnings:
        for warning in collect_markdown_warnings(src):
            print(f"警告: {warning}")
    pandoc = find_pandoc(args.pandoc)
    if args.resource_path:
        resource_path = args.resource_path
    else:
        resource_path = os.pathsep.join(str(path) for path in collect_image_resource_dirs(src))

    with tempfile.TemporaryDirectory(prefix="thesis_md_to_word_", ignore_cleanup_errors=True) as td:
        tmp_md = Path(td) / "preprocessed.md"
        tmp_images = Path(td) / "images"
        raw_docx = Path(td) / "pandoc_raw.docx"
        staged_out = Path(td) / "final_output.docx"
        print("正在预处理 Markdown...", flush=True)
        preprocess_markdown(src, tmp_md, tmp_images)
        print("正在调用 Pandoc 生成 Word 初稿...", flush=True)
        run_pandoc(tmp_md, raw_docx, reference, resource_path, pandoc)
        print("正在应用论文正文版式...", flush=True)
        stats = patch_docx_package(raw_docx, staged_out)
        print("正在整理公式、页眉页脚和参考文献编号...", flush=True)
        staged_out = run_word_postprocess(staged_out, reference)
        print("正在清理 Word 字体信息...", flush=True)
        normalize_word_xml_fonts_in_place(staged_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        replace_file_with_retry(staged_out, out)
        inspection = inspect_docx(out)
        if args.keep_temp:
            debug_dir = out.with_suffix("")
            debug_dir.mkdir(exist_ok=True)
            shutil.copy2(tmp_md, debug_dir / "preprocessed.md")
            shutil.copy2(raw_docx, debug_dir / "pandoc_raw.docx")

    print(f"output={out}")
    print(f"figures={stats.get('figures', 0)}")
    print(f"figure_captions={stats.get('figure_captions', 0)}")
    print(f"table_captions={stats.get('table_captions', 0)}")
    print(f"equations={stats.get('equations', 0)}")
    print(f"heading1={stats.get('heading1', 0)}")
    print(f"inspection={inspection}")
    if inspection["raw_tag"] or inspection["eq_markers"] or inspection["chinese_songti"]:
        raise RuntimeError(f"postprocess inspection failed: {inspection}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

---
name: pdf-reader
description: '读取并提取 PDF 文件中的文字。当用户要求读取、打开、提取或分析 PDF 文档时使用。支持中文和英文 PDF。自动将 PDF 页面转换为保留格式的可读文本。适用场景：阅读 PDF、提取 PDF 内容、将 PDF 转为文本、分析 PDF 文档。'
argument-hint: '[PDF file path]'
---

# PDF Reader

## Overview

Read and extract text content from PDF files. This skill handles PDF text extraction using either `pdfplumber` (better formatting preservation) or `pymupdf` (faster processing), both bundled in the skill's Python environment.

## When to Use

Use this skill when the user requests to:
- "Read this PDF"
- "Extract text from a PDF"
- "Convert PDF to text"
- "Analyze this PDF document"
- "Open this PDF and show me the content"
- Any request involving a `.pdf` file that needs text extraction

## Required Setup

The skill uses `uv` for Python environment management. Dependencies (`pdfplumber`, `pymupdf`) are declared in `pyproject.toml`.

If dependencies are not yet installed:
```bash
cd "{skill_path}" && uv sync
```

## Workflow

### Step 1: Confirm PDF Path

Ask the user for the PDF file path if not already provided. The path can be:
- An absolute path: `C:\Users\admin\Documents\paper.pdf`
- A relative path from current working directory

### Step 2: Extract Text

Run the bundled extraction script:

```bash
uv run python ./scripts/read_pdf.py "PATH_TO_PDF"
```

The script will:
1. Try `pdfplumber` first (better formatting preservation)
2. Fall back to `pymupdf` if pdfplumber fails
3. Print extracted text to stdout
4. Save extracted text to `ORIGINAL_FILENAME_extracted.txt` alongside the PDF

### Step 3: Present Results

Read the extracted text and present a summary or full content to the user based on their request. For long documents, provide a summary first and offer to show specific sections.

## Supported Formats

- PDF files with embedded text (both Chinese and English)
- Multi-page documents
- Text-based PDFs (not scanned/image-only PDFs — those need OCR)

## Notes

- Scanned/image-based PDFs without OCR text layer cannot be extracted with this tool
- Complex layouts (tables, multi-column) may result in imperfect text ordering
- The `*_extracted.txt` file is saved in the same directory as the original PDF

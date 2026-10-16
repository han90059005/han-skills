---
name: multi-source-review-consolidator
description: '将多份 AI 生成的复习笔记文件（txt/md）合并为一份结构化的 Markdown 复习文档。合并重复内容、去重词汇和语法知识点、按章节/课时统一排版，并可选择按类别（如语法/课文与词汇）拆分为多个文件。适用场景：合并多份 AI 生成的学习指南、把零散的复习笔记整合成一份文档、整理多个来源的课程复习资料、把合并后的复习拆分为语法和词汇部分。'
argument-hint: '[source directory path]'
---

# Multi-Source Review Consolidator

## Overview

Takes multiple AI-generated review note files (`.txt` / `.md`) from a course directory, intelligently merges them into one well-structured Markdown review document, then optionally splits into sub-files by category.

## When to Use

Use this skill when the user requests to:
- "把这几个文件合并成复习资料"
- "Consolidate these review files into one"
- "整理这些复习笔记"
- "把课文和单词分开"
- "Merge and organize these notes by lesson"
- Any request involving combining multiple scattered review/note files into a structured document

## Workflow

### Phase 1: Inventory & Read

**Step 1.1: List all candidate files**

```powershell
Get-ChildItem -Path "TARGET_DIR" | Where-Object { $_.Name -match '(复习|review|笔记|note|单词|vocab|语法|grammar|课文|text)' } | Select-Object Name
```

Files to include:
- AI-generated review notes (ChatGPT, Gemini, Claude, etc.)
- Existing partial vocabulary lists
- Existing partial grammar summaries
- Any `.txt` or `.md` file with course-related content

**Step 1.2: Read all files**

Read every candidate file in full using `read_file`. Do NOT skip any — each file may contain unique vocabulary or grammar points that others missed.

### Phase 2: Structure Identification

**Step 2.1: Identify the course structure**

From the source files, extract:
- Textbook name and edition
- Chapter/lesson boundaries (e.g., "第1课", "Lesson 1")
- Common section headers (基本课文, 核心语法, 生词表, 表达要点, etc.)

**Step 2.2: Build a merged outline**

Create a unified outline that covers all lessons/chapters in scope. For each lesson, the standard sections are:

```
## 第N课 Title
### 一、基本课文 (Basic Text)
### 二、核心语法 (Core Grammar)
### 三、表达要点 (Expression Notes)
### 四、生词表 (Vocabulary)
```

### Phase 3: Content Merging

**Step 3.1: Merge by lesson and section**

For each lesson + section combination:
1. Collect all entries from ALL source files
2. Deduplicate identical entries
3. Resolve conflicts (if Source A and Source B differ on a reading/translation, prefer the more detailed one)
4. Sort vocabulary by category (人物・职业, 场所, 物品, 动词, 时间, etc.)

**Step 3.2: Merge priority rules**

| Conflict | Resolution |
|----------|------------|
| Different readings for same word | Keep both if both are valid; otherwise prefer the one with more detail |
| Different Chinese translations | Keep the more common textbook translation |
| Missing reading in one source | Fill from the source that has it |
| Extra word in one source | Include it (it may be from the textbook) |

**Step 3.3: Add cross-reference supplements**

After merging, identify:
- High-frequency exam words → create a "必背高频词" list at the top
- Common grammar patterns → create a "考试冲刺重点" section
- PDF page references → add a "PDF 页码对照" table
- Common greetings/expressions → add an 附录

### Phase 4: Output Generation

**Step 4.1: Write the consolidated file**

Write to `大学日语复习资料.md` (or `[CourseName]复习资料.md`).

**Step 4.2: Optionally split by category**

If the user requests splitting, create:

| File | Content |
|------|---------|
| `[Name]-课文.md` | Basic texts, grammar, expressions, exam tips, greetings |
| `[Name]-单词.md` | All vocabulary tables, high-frequency word list, number/time tables |

### Phase 5: PDF Cross-Reference (Optional)

If a textbook PDF is available and the user wants page references:

**Step 5.1: Verify PDF page numbers**

Do NOT trust AI-generated page numbers. Extract the actual pages:
```python
import fitz
doc = fitz.open("textbook.pdf")
# Render suspect pages as images
page.get_pixmap(dpi=300).save(f"page_{n:03d}.png")
```

**Step 5.2: Read vocabulary from images**

Use `view_image` to visually read the word list pages. Cross-reference each entry against the merged vocabulary. Add any missing words.

**Step 5.3: Update page reference table**

Use the verified page numbers in the final document.

## Page Number Offset Pattern

For the 新版中日交流标准日本语 textbook:
- PDF page ≈ book printed page + 18 (offset varies by front matter)

**To find the exact offset:**
1. Find a page with a visible printed page number at the bottom
2. Note both the PDF page number and the printed book page number
3. Calculate: offset = PDF page - printed page

## Output Formatting Rules

1. **Tables use Markdown pipe syntax** with columns: `| 日语 | 读音 | 中文 |`
2. **Vocabulary grouped by category** under `###` subheadings
3. **Grammar points** use `####` for sub-points
4. **Exam-critical content** marked with ⭐ emoji
5. **Warnings** marked with ⚠
6. **Readings** in parentheses after kanji: `中国人（ちゅうごくじん）`

## Common Pitfalls

- **AI-generated page numbers are unreliable**: Always verify against the actual PDF before including page references
- **OCR on scanned PDFs is unreliable**: Use `view_image` for visual reading instead; manga-ocr and easyocr both struggle with textbook-quality scans
- **Source files may have different coverage**: One file may have more grammar, another more vocabulary — merge all, don't pick one
- **Word readings may differ between sources**: When in doubt, include both and note the ambiguity

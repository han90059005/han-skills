---
name: course-review-generator
description: '从课程 PPT（PDF）生成结构化复习笔记，或把多份已有的复习笔记/学习指南合并去重为一份 Markdown。支持扫描版 PDF 视觉回读与可选转 PDF。侧重复习资料本身的内容整理；交互式维护单份笔记用 makenote，依据文献写论文用 makepaper，最终排版转 PDF/Word 用 makelatex 或 makedocx。'
argument-hint: '[course directory path]'
---

# Course Review Generator

## Overview

Reads all course PPT slide PDFs from a directory, extracts text, and organizes key concepts into a structured review document (Markdown). Optionally converts the final Markdown to a formatted PDF using Pandoc.

## When to Use

Use this skill when the user requests to:
- "整理 PPT 复习资料"
- "Generate review notes from lecture slides"
- "Create a study guide from these PDFs"
- "Batch extract and organize course slides into notes"
- "从课件 PDF 生成复习清单"
- Any request involving generating structured review materials from course PPT PDFs
- "把这几个文件合并成复习资料"
- "整理这些复习笔记"
- "把课文和单词分开"
- 任何涉及「合并/去重多份已有复习笔记」的请求

## Prerequisites

Before using this skill, confirm:
- **Python** with `uv` is available (for PDF extraction)
- **Pandoc** ≥ 3.0 is installed (for Markdown → PDF conversion)
- **XeLaTeX** is installed (for Chinese PDF generation via Pandoc)

Check with:
```bash
pandoc --version
```

## Workflow

### Phase 0: Self-Improvement Rule ⭐

> **核心规则：Skill 自更新机制**

If this skill fails to execute successfully at any step (e.g., PDF extraction returns empty/watermark-only text, OCR tools cannot download, network blocked), and a **working workaround is discovered and validated**, you MUST update this SKILL.md file immediately to incorporate the fix. Examples:

| Failure | Workaround Found | Action |
|---------|-----------------|--------|
| pdfplumber returns only watermark text ("扫描全能王 创建") | Render PDF pages as PNG via `fitz.get_pixmap()`, read with `view_image` | Add Phase 1B to this skill |
| easyocr model download blocked by network | Use `view_image` for visual reading instead of OCR | Document fallback path |
| Pandoc Chinese font not found | Use `SimSun` or detect available CJK fonts | Update Phase 4 font config |

**Update procedure**: After fixing the issue and confirming it works, use `replace_string_in_file` or `insert_edit_into_file` to update this SKILL.md with the new steps, fallback paths, or troubleshooting entries. This ensures the skill grows more robust with each use.

---

### Phase 1: Scan & Classify

**Step 1.1: List all PDF files in the course directory**
```powershell
Get-ChildItem -Path "COURSE_PATH" -Filter "*.pdf" | Select-Object Name, Length
```
Ignore the textbook PDF (e.g., "数字电子技术基础 第6版..."). Only process lecture slide PDFs.

**Step 1.2: Detect PDF type — text-based or scanned image**
Try extracting text from one representative PDF first:
```powershell
uv run python "PATH_TO_PDF_READER_SCRIPT" "COURSE_PATH\sample.pdf"
```
Then check the `_extracted.txt` file. Follow the decision tree:

```
_extracted.txt 内容？
├── 有实质性文字内容（如"第X章"、"定义"、"公式"等）
│   └── ✅ 文本版 PDF → 继续 Phase 2（文本提取 + 整理）
│       按原流程：foreach 所有 PDF 执行 pdf-reader 提取
│
└── 仅有水印文字（如"扫描全能王 创建"）或 0 字符
    └── 🔴 扫描图片版 PDF → 进入 Phase 1B（视觉阅读）
        跳过 pdf-reader 批量提取，直接按 Phase 1B 处理
```

> **Encoding note**: If extraction prints have garbled characters in the terminal (Windows GBK issue), the `.txt` files themselves are UTF-8 and will be fine.

### Phase 1B: Visual Reading for Scanned PDFs

> 适用条件：PDF 为扫描图片版，pdfplumber/pymupdf 无法提取文本。

**Step 1B.1: Render PDF pages to images**

使用 PyMuPDF（fitz）将每章 PDF 逐页渲染为 PNG 图片（150 DPI 平衡清晰度与速度）：

```powershell
cd "PATH_TO_PDF_READER_SKILL"
uv run python -c "
import fitz, os
pdf_path = r'COURSE_PATH\CHAPTER.pdf'
out_dir = os.path.splitext(pdf_path)[0] + '_pages'
os.makedirs(out_dir, exist_ok=True)
doc = fitz.open(pdf_path)
for i in range(len(doc)):
    pix = doc[i].get_pixmap(dpi=150)
    pix.save(os.path.join(out_dir, f'page_{i+1:02d}.png'))
doc.close()
print(f'Done: {len(doc)} pages -> {out_dir}')
"
```

PyMuPDF is bundled in the pdf-reader skill's `.venv` — no extra installation needed. Does NOT require poppler or GhostScript.

**Step 1B.2: Read images with view_image**

Use `view_image` to visually read PPT slide content page by page. **Strategy for large chapters:**

| 策略 | 做法 |
|------|------|
| **开头几页** | 逐页阅读：标题页 → 目录页 → 概述页，确定章节结构 |
| **中间内容** | 跳读：每隔 2~5 页抽读，抓取关键概念和公式 |
| **结尾几页** | 逐页阅读：小结/对比表/例题，把握考点 |

- 每次 `view_image` 可并行调用 3~5 张图片
- 分批阅读，每批读完后立即整理要点
- 总页数 > 30 的章节必须采用跳读策略

**Step 1B.3: Write batch results**

读完一批后立即用 `replace_string_in_file` 追加到复习文件，**不积累**。章节分隔符：

```markdown
> 📌 第X章复习要点整理完毕，接下来进入第Y章。
```

### Phase 2: Read & Organize (by Chapter Batch)

**Step 2.1: Group chapters into batches**

Group PDFs logically — typically each chapter has 1~7 parts. Process **one batch at a time** to avoid context overflow.

Example batching:
```
Batch 1: Chapter 1 + Chapter 2 (5 files)
Batch 2: Chapter 4 (7 files)
Batch 3: Chapter 5 (3 files)
Batch 4: Chapter 6 (5 files)
Batch 5: Chapter 7 + 8 + 9 (5 files)
```

**Step 2.2: Read each batch and extract key points**

For text-based PDFs, read the extracted `.txt` files with `read_file`. For scanned PDFs from Phase 1B, `view_image` is used directly.

Identify:
- Chapter/section titles and hierarchy
- **Key formulas** (特征方程, 动力学方程, 组成方程)
- **Feature tables** (对比表, 分类表, 条件表)
- **Core concepts** and definitions
- **Design methods** and analysis steps
- **Typical ICs** and their pin functions (74138, 7490, etc.) — for EE courses
- **Polymer structures, mechanisms** — for chemistry courses
- Important problem types marked ⭐

**Step 2.3: Write batch results immediately**

After reading each batch, use `replace_string_in_file` to append to the output Markdown file. Use the chapter separator pattern:

```markdown
> 📌 第X章复习要点整理完毕，接下来进入第Y章。
```

Replace this placeholder with both the new content AND the next placeholder.

### Phase 3: Document Structure

The output Markdown file should follow this structure:

```markdown
# 📘 课程名称 — 复习清单

> 教材：XXX | 总学时：XX H | 考试形式：闭卷

---

## 第X章 章节名称

### X.1 子主题
- Key point 1
- Key point 2

#### 重点表格
| 列1 | 列2 | 列3 |

### X.2 子主题 ⭐
- Important formula: $Q^{n+1} = ...$
```

**Formatting conventions:**
- Use `⭐` to mark **exam-critical** topics
- Use Markdown tables for comparisons, truth tables, feature tables
- Use `$LaTeX$` for all mathematical formulas (Pandoc compatible)
- Use `**bold**` for key terms on first mention
- Keep content concise — bullet points, not paragraphs
- Include IC pin tables where relevant

### Phase 4: Generate PDF (Optional)

After the Markdown is complete, convert to PDF:

```powershell
pandoc "REVIEW_FILE.md" -o "REVIEW_FILE.pdf" `
  --pdf-engine=xelatex `
  -V mainfont="SimSun" `
  -V CJKmainfont="SimSun" `
  -V monofont="Consolas" `
  --metadata title="课程名称 复习资料" `
  -V geometry:margin=2cm
```

**Common Pandoc PDF issues:**
| Issue | Fix |
|-------|-----|
| `\$` not rendered as math | Replace `\$` with `$` in `.md` file |
| Emoji missing in font | Remove emoji before conversion |
| Chinese not rendering | Ensure `--pdf-engine=xelatex` and CJK font set |
| `! Missing $ inserted` | Remove extra `$` escapes around math |

## 模式二：合并多份复习笔记

当用户要求「把这几个文件合并成复习资料」「整理这些复习笔记」「按课时合并笔记」时，走本模式（而非从 PPT 生成）。

### 1. 盘点并读取候选文件

```powershell
Get-ChildItem -Path "TARGET_DIR" | Where-Object { $_.Name -match '(复习|review|笔记|note|单词|vocab|语法|grammar|课文|text)' } | Select-Object Name
```

纳入所有 AI 生成的复习笔记、零散单词表、语法总结等 `.txt` / `.md`，逐份完整读取，不跳过——每份可能含有别处没有的知识点。

### 2. 识别课程结构

从源文件提取教材名称、章节/课时边界、常见小节标题，建立统一大纲：

```markdown
## 第N课 标题
### 一、基本课文
### 二、核心语法
### 三、表达要点
### 四、生词表
```

### 3. 按课时与小节合并

- 同一「课时+小节」：汇总所有来源条目 → 去重 → 冲突时保留信息更全的一条；
- 生词按类别（人物/场所/物品/动词/时间…）排序；
- 某来源缺读音/翻译时，从有该信息的来源补齐。

冲突处理：同一词读音不一致 → 都有效则都保留，否则取更详细者；中文翻译不一致 → 取教材常用译法。

### 4. 补充交叉信息

按需追加：高频必背词表、考试冲刺重点、PDF 页码对照表、常见表达附录。

### 5. 输出

- 写入 `[课程名]复习资料.md`；
- 可拆分：`[课程名]-课文.md`、`[课程名]-单词.md`。

### 页码校验（可选）

AI 给的页码不可信：用 PyMuPDF 把对应页渲染成 PNG，再用 `view_image` 目视核对，算出偏移量（偏移 = PDF 页码 − 书页页码）。

### 输出格式规范

- 表格用 Markdown 管道语法（如 `| 日语 | 读音 | 中文 |`）；
- 生词按类别归到 `###` 小节；
- ⭐ 标记必考、⚠ 标记易错；
- 读音用括号附在词后：`中国人（ちゅうごくじん）`。

## Key Principles

1. **Detect PDF type first**: Always test one PDF before batch processing. If only watermark text → switch to visual reading (Phase 1B).
2. **Batch processing**: Read one chapter at a time, write immediately — never accumulate
3. **Math formatting**: Use `$...$` for inline, `$$...$$` for display math
4. **Tables over prose**: Use Markdown tables for any comparative/structural information
5. **Star what matters**: Mark ⭐ on:
   - 特征方程 (characteristic equations)
   - 功能表/真值表 (function/truth tables)
   - 设计方法 (design methods)
   - 典型芯片 (typical ICs like 74138, 7490, 555)
   - 核心机理/动力学方程（化学类）
6. **Skip textbook PDFs**: Only process lecture slide PDFs, ignore reference book PDFs
7. **Self-update on failure**: If any step fails and you find a working workaround, update this SKILL.md immediately (see Phase 0).

## Troubleshooting

| Problem | Likely Cause | Solution |
|---------|-------------|----------|
| `_extracted.txt` all "扫描全能王 创建" | PDF is scanned images | Go to Phase 1B (visual reading) |
| `_extracted.txt` 0 characters | Scanned PDF with no text layer | Go to Phase 1B |
| `winget install Tesseract` fails | Network blocks GitHub downloads | Skip OCR, use Phase 1B visual reading |
| `easyocr` model download SSL error | Network/proxy blocks HTTPS | Skip OCR, use Phase 1B visual reading |
| `pdf2image` needs poppler | System lacks poppler | Use `fitz.get_pixmap()` instead (bundled) |
| Pandoc Chinese not rendering | Missing CJK font config | Use `--pdf-engine=xelatex` + `-V CJKmainfont="SimSun"` |

## Output Files

All generated in the course directory:
- `课程复习资料.md` — Structured review notes in Markdown
- `课程复习资料.pdf` — Formatted PDF (if Phase 4 executed)

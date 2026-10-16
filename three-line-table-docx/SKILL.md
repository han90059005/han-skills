---
name: three-line-table-docx
description: '将 Markdown 转换为带三线表格式的 Word（.docx）。先用 pandoc 进行初步转换，再用 python-docx 应用中文论文标准表格边框：上下粗线（1.5pt）、表头分隔细线（0.75pt）、无竖线和内部横线。当用户要求将 .md 转为带三线表格式的 .docx，或需要生成表格排版规范的 Word 文档时使用。'
user-invocable: true
argument-hint: 'Path to markdown file to convert'
---

# Markdown → Word（三线表格式）

## 触发条件

- 用户要求将 Markdown 转为 Word
- 用户要求三线表表格格式
- 用户要求生成 .docx 且涉及表格

## 工作流程

### 步骤 1：Pandoc 转换 Markdown → Docx

```powershell
pandoc "path\to\file.md" -o "path\to\file.docx"
```

### 步骤 2：Python 脚本施加三线表格式

三线表标准（中国学术规范）：
- **顶线**：1.5pt 粗线（sz=12）
- **表头下线**：0.75pt 细线（sz=6）
- **底线**：1.5pt 粗线（sz=12）
- **无竖线**、**无内部横线**

```powershell
uv run --with python-docx python "<script>" "<input.docx>" "<output.docx>"
```

### 步骤 3（文件被锁时）

若 `.docx` 被 Word 占用导致 `Permission denied`：
```powershell
# 另存为新文件名
uv run --with python-docx python "<script>" "<input.docx>" "<output_三线表.docx>"
```

## Python 格式化脚本

脚本路径：与此 SKILL.md 同目录的 `format_three_line.py`

核心函数：
- `apply_three_line_table(table)` — 对单个表格施三线表边框
- `set_cell_border(cell, **kwargs)` — 设置单元格边框

## 注意事项

- Pandoc 生成的 docx 默认表格含全部边框，需要 python-docx 后处理
- 先检查 pandoc 是否安装（`pandoc --version`）
- 中文路径需用引号包裹
- python-docx 临时安装用 `uv run --with python-docx`

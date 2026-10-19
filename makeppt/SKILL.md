---
name: makeppt
description: 把一个 Markdown 文件（实验报告/论文/大纲/讲义等）转成汇报用演示文稿，同时产出 PDF（LaTeX Beamer，默认 NWPU 模板）和可编辑 .pptx。固定流程：先读 md 出「提纲」给用户审查，通过后智能提炼成逐页要点，再分别编译 PDF、生成 pptx。硬规则：文字颜色≤3种、每页有页码、文字清晰可读、单页文字克制。默认 NWPU 模板，md 无西工大内容或用户要求时才用通用模板。侧重演示文稿成品输出；写论文用 makepaper、做笔记用 makenote、转 Word 用 makedocx。触发词：「makeppt」「生成PPT」「md转PPT」「做汇报PPT」「把这份 md 做成 PPT」。
---

# makeppt（Markdown → 汇报 PPT）

把一个 Markdown 文件转成汇报用演示文稿，一次产出两份：**PDF**（LaTeX Beamer）和 **.pptx**（可编辑）。默认使用西北工业大学（NWPU）Beamer 模板。

## 与其他技能的区别

- 本技能：md → PPT（PDF + pptx），定位是「成品 / 输出层」。
- makepaper：依据文献 md 写论文/综述；makenote：交互维护笔记；course-review-generator：批量生成复习笔记。
- makelatex / makedocx：只把 md/tex 转成 PDF / Word，不做演示文稿。

## 固定流程（每次必走）

1. **读 md**：解析标题、章节、表格、图片、公式，以及元数据（姓名 / 学号 / 学院 / 日期）。源 md 只读、不改。
2. **出提纲**（必须，不可跳过）：给用户一份「每页标题 + 3~5 个要点 + 配图/表格位置」的提纲，等用户确认或修改，**改到用户 OK 才继续**；未经确认不得直接生成成品。
3. **写内容**：按批准的提纲智能提炼，文字精炼、每页一个核心观点，不放大段。
4. **生成两份文件**：
   - PDF：写 `main.tex` → `scripts/compile_pdf.ps1` 编译。
   - pptx：写 `slides.json` → `scripts/make_pptx.py` 生成。
5. **交付**：两份都存到 md 同目录，命名 `汇报PPT-<标题>-<姓名>.pdf` / `.pptx`（无姓名则省略 `<姓名>-`）。

## 模板选择

- 默认 NWPU Beamer 模板（`D:\AI-tools\NWPU-BEAMER-main`）。
- md 里没有西工大相关内容、或用户明说不用 NWPU 时，改用通用简洁模板（去掉校徽/校名背景，主题色可用 NWPU 蓝或中性蓝）。

## 样式硬规则（不可违反）

1. **文字颜色 ≤ 3 种**：正文黑、标题栏白、最多一个强调色；蓝色只做背景/色块，不算文字色。
2. **每页有页码**：Beamer 页脚「第 x / 共 y 页」；pptx 底部右下加 `x / y`。
3. **文字清晰可读**：正文字号够大、对比度足够，不放小字；有文字的地方一定让人看清。
4. **单页文字克制**：要点精炼，每页 3~5 条为宜。

## 生成 PDF（LaTeX Beamer）

1. **组装构建目录**（放系统临时目录，例如 `$env:TEMP\makeppt-<slug>\`）：
   - 复制 NWPU 模板全部内容到构建目录（需要 `nwpubeamer.sty`、`source/` 背景与校徽素材）；
   - 把 md 里 `![](...)` 引用的图片复制到构建目录 `figures\`（保持 md 里的相对文件名）；
   - 写 `main.tex`：`\documentclass[aspectratio=169,fontset=fandol]{ctexbeamer}` + `\usepackage{nwpubeamer}` + 逐页 `frame`。
2. **编译并交付**：

   ```powershell
   powershell -File "C:\Users\admin\.agents\skills\makeppt\scripts\compile_pdf.ps1" -BuildDir "<构建目录>" -Out "<目标 PDF 路径>"
   ```

   脚本自动设 TeX Live PATH、跑两遍 XeLaTeX、把 `main.pdf` 交付到 `-Out`。

3. 编译后清理临时构建目录（除非用户要保留 LaTeX 源码）。

## 生成 pptx（python-pptx）

1. 写 `slides.json`（结构见下）。
2. 运行：

   ```powershell
   & "C:\Users\admin\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" "C:\Users\admin\.agents\skills\makeppt\scripts\make_pptx.py" "<slides.json>" -o "<目标 pptx 路径>"
   ```

### slides.json 结构

```json
{
  "title": "主标题",
  "subtitle": "副标题（可省略）",
  "author": "姓名（可省略）",
  "affiliation": "单位（可省略）",
  "date": "日期/备注（可省略）",
  "logo": "标题页 logo 图片路径（可省略）",
  "slides": [
    {
      "title": "页标题",
      "bullets": ["要点1", "要点2"],
      "table": { "headers": ["列1", "列2"], "rows": [["a", "b"], ["c", "d"]] },
      "image": "图片路径（可省略）",
      "caption": "图注（可省略）"
    }
  ]
}
```

- `bullets` / `table` / `image` / `caption` 可同时出现，脚本按 要点 → 表格 → 图片 → 图注 的顺序垂直排布。
- 图片路径用绝对路径、或相对 `slides.json` 所在目录的相对路径均可；缺图会在对应页显示 `[缺图]` 提示，不静默跳过。

## 公式与图片

- **PDF**：公式用原生 LaTeX（`$...$`、`\[...\]`、`aligned` 等）；图片 `![](...)` 相对路径自动复制进 `figures/`。
- **pptx**：行内/显示公式退化为 Unicode 文本（下标 ₀₁₂ₙ、希腊字母 λ Đ、运算符 ≈ × − 等），精确排版以 PDF 为准；若必须精确，把该公式用 LaTeX 单独渲染成透明 PNG 后作为图片插入。
- **图片**：md 引用的图片复制进 `figures/`；**缺图要明确报出来**，不要静默失败。

## 依赖

| 依赖 | 用途 | 说明 |
| --- | --- | --- |
| TeX Live（xelatex） | 编译 PDF | `D:\AI-tools\latex\texlive\2026\bin\windows` |
| NWPU 模板 | Beamer 主题 | `D:\AI-tools\NWPU-BEAMER-main` |
| python-pptx | 生成 pptx | bundled Python（见 load_workspace_dependencies） |

## 禁止项

1. 未经用户批准提纲就直接生成成品。
2. 单页堆大段文字 / 放小字 / 超过 3 种文字颜色 / 缺页码。
3. 图片缺文件时静默跳过。
4. 改动源 md 文件。

---
name: thesis-md-to-word
description: Export the thesis Markdown in this GraduationThesis workspace to a school-formatted Word document. Use when converting thesis body `.md` files to `.docx`, keeping Pandoc native equations, using image alt text as the only figure caption source, keeping equation numbers on the same line as the equation, forcing chapter page breaks, restoring the template header exactly, and normalizing WPS-friendly Chinese font names.
---

# Thesis Md To Word

Follow this workflow exactly.

## Workflow

1. Use `scripts/export_thesis_docx.py` as the only entrypoint.
2. Use `assets/reference.docx` as `--reference-doc`.
3. Let Pandoc convert Markdown, tables, images, and OMML equations first. Disable Pandoc `subscript` so common ranges such as `30~50` and `1~2` stay normal text.
4. Apply only safe OOXML edits after Pandoc.
5. Run `scripts/word_postprocess.ps1` at the end for Word COM cleanup.

## Required Behavior

- Keep Pandoc native equations. Do not convert equations to images.
- Use image Markdown alt text as the only figure caption source.
- Drop the duplicated `Figure x-x ...` text line immediately after an image from the final DOCX caption flow.
- Keep table captions from body text lines such as `表x-x ...`.
- Make figure captions centered at 10.5 pt.
- Make table captions centered and SimHei at 10.5 pt without bold.
- Format normal Markdown tables as three-line tables: top border, header bottom border, final bottom border; table text centered, SimSun 10.5 pt. If every first-row cell is a single logical line, keep the first row compact with a fixed small height instead of letting Word expand it because of automatic wrapping.
- Leave one blank line before and after figures and tables.
- Keep displayed equations centered.
- Force all equations to small-four size (`12 pt`). Latin math glyphs should render as `Times New Roman`; Chinese glyphs inside formulas should use `SimSun`.
- Keep equation numbers on the same visual line as the equation and push them to the far right, preserving chapter numbering like `(2-1)`.
- Build numbered displayed equations with a borderless two-column table: the left cell holds the centered equation and the right cell holds the far-right, right-aligned number.
- Start every chapter on a new page.
- Keep code blocks at 12 pt. Chinese text must use `SimSun`; English letters and numbers must use `Times New Roman`, not monospace fonts.
- Indent every code paragraph by exactly two Chinese-character widths so it visually matches the body-text first-line indent.
- Force code paragraphs to `Bold = off`.
- Do not bold SimHei title text. Chapter titles, section titles, subsection titles, and table titles should stay SimHei without bold.
- Normalize Chinese font names to `SimSun` and `SimHei` in package XML.
- Restore headers from the school template exactly.
- Keep paragraph before/after spacing at zero. Use blank paragraphs for required visual gaps instead of paragraph spacing values.
- For title blocks such as `摘要`, `目录`, and chapter titles, use exactly two blank small-four lines before the title and one blank small-four line after it.

## Command

```powershell
python "D:\\Desktop\\GraduationThesis\\.agents\\skills\\thesis-md-to-word\\scripts\\export_thesis_docx.py" `
  --input "D:\\Desktop\\GraduationThesis\\paper-body\\body.md" `
  --output "D:\\Desktop\\thesis-output.docx" `
  --reference "D:\\Desktop\\GraduationThesis\\.agents\\skills\\thesis-md-to-word\\assets\\reference.docx"
```

Use `--keep-temp` only for debugging intermediate artifacts.

## Validation

- Check stdout counts first.
- Open the exported `.docx` through Word COM and confirm it opens cleanly.
- Confirm `OMaths.Count` is non-zero.
- Artifact-tool preview may hide OMML equations; do not treat that alone as a DOCX failure when Word opens the file correctly.

## Constraints

- This workflow is Windows-only.
- It requires local Pandoc. Microsoft Word COM is optional and disabled by default in the packaged app.
- Do not use the old `.dotx` style-pack files as `reference-doc`; they were verified to produce damaged output.

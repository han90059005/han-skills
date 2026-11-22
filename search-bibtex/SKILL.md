---
name: search-bibtex
description: Use when the user provides one or more academic PDF files or an existing BibTeX file and wants the search-bibtex binary to extract metadata, fuzzy-search bibliographic sources, refresh BibTeX, rank candidates with configurable source priority, load defaults from config.toml, and present an interactive Vim-key selection UI. Handles computer science preprints, conference papers, and journal papers through an independent CLI; does not depend on Paperlib.
---

# Search BibTeX

Use this skill for the `search-bibtex` binary. The binary is independent of Paperlib. Grok search may be used while improving or debugging this project, but it must stay out of the CLI runtime and skill workflow.

## Workflow

1. Confirm the binary is available:

   ```bash
   search-bibtex --help
   ```

2. Inspect PDF metadata and generated search queries:

   ```bash
   search-bibtex metadata <pdf-path>
   ```

3. Search and rank candidates. In a TTY, `search` opens the selector; when piped, it prints JSON:

   ```bash
   search-bibtex search <pdf-path> --limit 10 --timeout 30 --source-priority dblp,arxiv,crossref,openalex,doi
   ```

   Parallel source search is enabled by default. Use `--no-parallel` only when serial lookup is explicitly wanted. If the user has a config file, pass `--config <path>` and let CLI flags override it.

4. For title strings instead of PDFs, use `search-bibtex search-title`. Multiple titles in one input are split by `;` by default, and stdin is accepted when no title argument is provided.

5. Let the user choose a BibTeX entry:

   ```bash
   search-bibtex select <pdf-path> --limit 10 --timeout 30 --source-priority dblp,arxiv,crossref,openalex,doi
   ```

6. If the user already has a `.bib` file and wants refreshed fields without changing citation keys:

   ```bash
   search-bibtex update <bibtex-path> --in-place
   ```

7. For non-interactive use, select by ranked index:

   ```bash
   search-bibtex select <pdf-path> --select-index 0 --format bibtex
   ```

## Source Priority

The built-in default source order is:

```text
dblp,arxiv,crossref,openalex,doi,semantic-scholar
```

For computer science papers, this order avoids Semantic Scholar's anonymous rate limits:

```bash
--source-priority dblp,arxiv,crossref,openalex,doi
```

Include `semantic-scholar` only when the user wants it or the local environment can tolerate anonymous API rate limits:

```bash
--source-priority dblp,arxiv,crossref,openalex,semantic-scholar,doi
```

Use `--weights` when ranking behavior should change:

```bash
--weights title=0.5,author=0.2,year=0.1,identifier=0.15,source=0.05
```

`search-bibtex config-template` prints a TOML starter file. Config files can add custom HTTP sources and include their names in `source_priority`. Full config docs are in `docs/CONFIGURATION.md`.

## Interaction

The interactive selector supports:

- `j` / `k` or arrow keys to move.
- `g` / `G` to jump to first or last visible candidate.
- `/` to filter candidates.
- `Enter` to select.
- `q`, `Esc`, or `Ctrl-C` to cancel.

Render UI goes to stderr and selected BibTeX or JSON goes to stdout. When the user presses `Enter`, the screen shows formatted BibTeX and the tool attempts to copy it to the clipboard if a local clipboard command is available.

## Failure Handling

Do not hide source failures. `search` returns explicit `sourceErrors`; `select` prints source errors to stderr before selection. If no candidates are returned, surface the CLI error instead of fabricating a BibTeX entry.


## 本机约定：写完文章后说「再勘误一下」

用户写完论文/综述后会说「再勘误一下」，此时按下面的顺序核查参考文献，不要只改错别字、也不要跳过检索：

1. 定位文献表：Markdown 里 `## 参考文献`（或 `References`）之后的 `[n]` 条目，即 makepaper 的产出格式。
2. 逐条抽标题，汇总成一批用分号连接：

   ```bash
   search-bibtex search-title "标题1; 标题2; 标题3" --limit 5 --timeout 30
   ```

   条目多时按 10~15 条一批，避免单批请求过久。

3. 对照每条结果分三类：
   - **查不到**：无候选，或 `sourceErrors` 显示全部源失败 → 标「疑似幻觉/检索失败」，把标题原样列给用户，不要擅自改写。
   - **冲突**：标题相似但年份、作者、会议/期刊不一致 → 标「元数据冲突」，并列出现有值与检索到的值。
   - **一致**：标题、作者、年份都对得上 → 通过。
4. **先出清单再动手**：给出「通过 / 冲突 / 查不到」三栏，冲突项附建议值，等用户点头再改 md。
5. 确认后只改文献表，保持 `[n]` 编号与正文角标对应；除非用户明确要求，不要重排编号。若确实要重排，顺手核对正文所有 `[n]`。
6. 顺手做两项一致性检查：正文引用了但文献表里不存在的编号；文献表里有但全文从未被引用的条目（makelatex 编译时也会提示这两类）。

注意：`search-bibtex` 的源偏计算机领域（dblp 权重最高）。材料、高分子、化学类文献建议临时把 `crossref`、`openalex` 提前：

```bash
search-bibtex search-title "标题" --source-priority crossref,openalex,doi,dblp,arxiv
```

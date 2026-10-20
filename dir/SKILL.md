---
name: dir
description: 把一个目录打包成结构化的 LLM prompt，用于从零生成目录/项目骨架，或审查、优化已有目录；尊重 .gitignore，支持行号与 Markdown/XML 输出。当用户要求“生成/创建项目目录结构”“优化/整理/审查目录”或“把目录转成 prompt”时使用。
---

# dir

把整个目录打包成一份 prompt，在完整上下文中生成或优化目录。

## 何时使用

- 生成：用户要新建一个目录或项目骨架。
- 优化：用户要审查、整理、改进已有目录。

## 核心命令

用 `scripts/snapshot.py` 生成快照（只读，不修改原目录）：

```bash
python scripts/snapshot.py <目录> --markdown -o <快照文件>.md
```

常用选项：

- `--markdown`：输出带语言标签的 Markdown 代码块，适合模型阅读。
- `--cxml`：输出 Claude XML 格式。
- `-o <文件>`：写入文件而非标准输出。
- `--include-hidden`：包含 `.` 开头的隐藏文件/目录。
- `-e <扩展名>`：只打包某类文件，可重复。
- `--ignore "<fnmatch>"`：忽略匹配项，可重复。
- `--ignore-gitignore`：不读 `.gitignore`，打包全部文件。
- `--line-numbers`：加行号。

快照默认尊重 `.gitignore`（含 `!` 取反、按目录作用域），UTF-8 读取，二进制文件自动跳过。

## 两种模式

- 生成目录：先读 `references/generate.md`。
- 优化目录：先读 `references/optimize.md`。

## 边界

快照是只读的。优化目录时默认先给改动方案、经用户确认后再修改；删除或移动文件前先列出明确的目标路径。不要擅自覆盖目标目录里已有的同名文件，先提示。

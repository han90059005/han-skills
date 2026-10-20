#!/usr/bin/env python3
"""Concatenate a directory of files into a single prompt.

Dependency-free, bundled version of files-to-prompt for the ``dir`` skill.
Reads everything as UTF-8, honours .gitignore (including ``!`` negation and
per-directory scoping), skips binary files, and supports plain, Markdown and
Claude XML output.
"""

import argparse
import os
import sys
from fnmatch import fnmatch

EXT_TO_LANG = {
    "py": "python",
    "c": "c",
    "h": "c",
    "cc": "cpp",
    "cpp": "cpp",
    "cxx": "cpp",
    "hpp": "cpp",
    "java": "java",
    "js": "javascript",
    "jsx": "jsx",
    "ts": "typescript",
    "tsx": "tsx",
    "html": "html",
    "htm": "html",
    "css": "css",
    "scss": "scss",
    "xml": "xml",
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "md": "markdown",
    "markdown": "markdown",
    "rst": "rst",
    "txt": "text",
    "sh": "bash",
    "bash": "bash",
    "zsh": "bash",
    "rb": "ruby",
    "go": "go",
    "rs": "rust",
    "php": "php",
    "swift": "swift",
    "kt": "kotlin",
    "kts": "kotlin",
    "scala": "scala",
    "r": "r",
    "sql": "sql",
    "toml": "toml",
    "ini": "ini",
    "cfg": "ini",
}


def read_gitignore(directory):
    """Return non-comment, non-empty patterns from ``directory/.gitignore``."""
    gitignore_path = os.path.join(directory, ".gitignore")
    if not os.path.isfile(gitignore_path):
        return []
    with open(gitignore_path, "r", encoding="utf-8") as f:
        return [
            line.strip()
            for line in f
            if line.strip() and not line.startswith("#")
        ]


def is_ignored(path, rules):
    """Return True if ``path`` is ignored by a list of gitignore rules.

    ``rules`` is a list of pattern strings. A pattern may start with ``!`` to
    re-include a previously ignored path, and may end with ``/`` to match
    directories only. Patterns are matched against the entry's name (basename);
    patterns containing a ``/`` are not supported and never match. Later rules
    take precedence over earlier ones.
    """
    name = os.path.basename(path)
    is_dir = os.path.isdir(path)
    ignored = False
    for rule in rules:
        negate = rule.startswith("!")
        pattern = rule[1:] if negate else rule
        if not pattern:
            continue
        dir_only = pattern.endswith("/")
        pattern = pattern.rstrip("/")
        if not pattern or "/" in pattern:
            continue
        if dir_only and not is_dir:
            continue
        if fnmatch(name, pattern):
            ignored = not negate
    return ignored


def add_line_numbers(content):
    lines = content.splitlines()
    padding = len(str(len(lines)))
    return "\n".join(f"{i + 1:{padding}}  {line}" for i, line in enumerate(lines))


def language_for_path(path):
    """Guess a Markdown code-fence language tag for a file path."""
    name = os.path.basename(path)
    lower_name = name.lower()
    if lower_name in ("dockerfile", "makefile", "gemfile"):
        return lower_name
    if "." not in name:
        return ""
    return EXT_TO_LANG.get(name.rsplit(".", 1)[-1].lower(), "")


def print_path(writer, path, content, cxml, markdown, line_numbers, index):
    if cxml:
        print_as_xml(writer, path, content, line_numbers, index)
    elif markdown:
        print_as_markdown(writer, path, content, line_numbers)
    else:
        print_default(writer, path, content, line_numbers)


def print_default(writer, path, content, line_numbers):
    writer(path)
    writer("---")
    if line_numbers:
        content = add_line_numbers(content)
    writer(content)
    writer("")
    writer("---")


def print_as_xml(writer, path, content, line_numbers, index):
    writer(f'<document index="{index}">')
    writer(f"<source>{path}</source>")
    writer("<document_content>")
    if line_numbers:
        content = add_line_numbers(content)
    writer(content)
    writer("</document_content>")
    writer("</document>")


def print_as_markdown(writer, path, content, line_numbers):
    lang = language_for_path(path)
    backticks = "```"
    while backticks in content:
        backticks += "`"
    writer(path)
    writer(f"{backticks}{lang}")
    if line_numbers:
        content = add_line_numbers(content)
    writer(content)
    writer(backticks)


def print_file(path, writer, cxml, markdown, line_numbers, index):
    """Print a single file, warning and skipping unreadable content."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        print(f"Warning: Skipping file {path} due to UnicodeDecodeError", file=sys.stderr)
        return index
    except OSError as error:
        print(f"Warning: Skipping file {path}: {error}", file=sys.stderr)
        return index
    print_path(writer, path, content, cxml, markdown, line_numbers, index)
    return index + 1


def process_directory(
    path,
    inherited_rules,
    extensions,
    include_hidden,
    ignore_files_only,
    ignore_gitignore,
    ignore_patterns,
    writer,
    cxml,
    markdown,
    line_numbers,
    index,
):
    rules = list(inherited_rules)
    if not ignore_gitignore:
        rules.extend(read_gitignore(path))

    try:
        with os.scandir(path) as it:
            entries = [
                (entry.name, entry.path, entry.is_dir(follow_symlinks=False))
                for entry in it
                if not (entry.is_symlink() and os.path.isdir(entry.path))
            ]
    except OSError:
        return index
    entries.sort(key=lambda item: item[0])

    dirs = []
    files = []
    for name, entry_path, is_dir in entries:
        if not include_hidden and name.startswith("."):
            continue
        if not ignore_gitignore and is_ignored(entry_path, rules):
            continue
        if ignore_patterns:
            if is_dir:
                if not ignore_files_only and any(
                    fnmatch(name, pattern) for pattern in ignore_patterns
                ):
                    continue
            elif any(fnmatch(name, pattern) for pattern in ignore_patterns):
                continue
        if is_dir:
            dirs.append(entry_path)
        else:
            files.append(entry_path)

    if extensions:
        files = [
            file_path
            for file_path in files
            if os.path.basename(file_path).endswith(tuple(extensions))
        ]

    for file_path in files:
        index = print_file(file_path, writer, cxml, markdown, line_numbers, index)

    for dir_path in dirs:
        index = process_directory(
            dir_path,
            rules,
            extensions,
            include_hidden,
            ignore_files_only,
            ignore_gitignore,
            ignore_patterns,
            writer,
            cxml,
            markdown,
            line_numbers,
            index,
        )
    return index


def process_path(
    path,
    extensions,
    include_hidden,
    ignore_files_only,
    ignore_gitignore,
    inherited_rules,
    ignore_patterns,
    writer,
    cxml,
    markdown,
    line_numbers,
    index,
):
    if os.path.isfile(path):
        return print_file(path, writer, cxml, markdown, line_numbers, index)
    if os.path.isdir(path):
        return process_directory(
            path,
            inherited_rules,
            extensions,
            include_hidden,
            ignore_files_only,
            ignore_gitignore,
            ignore_patterns,
            writer,
            cxml,
            markdown,
            line_numbers,
            index,
        )
    return index


def read_paths_from_stdin(use_null_separator):
    if sys.stdin.isatty():
        return []
    content = sys.stdin.read()
    if use_null_separator:
        return [p for p in content.split("\0") if p]
    return content.split()


def main(argv=None):
    # Emit UTF-8 regardless of the console codepage so non-ASCII file content
    # (and warnings) never get mangled when stdout/stderr are piped.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass

    parser = argparse.ArgumentParser(
        prog="snapshot.py",
        description="Concatenate a directory of files into a single prompt.",
    )
    parser.add_argument("paths", nargs="*", help="Files or directories to include")
    parser.add_argument(
        "-e",
        "--extension",
        action="append",
        default=[],
        dest="extensions",
        help="Only include files with this extension (repeatable)",
    )
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include files and folders starting with '.'",
    )
    parser.add_argument(
        "--ignore-files-only",
        action="store_true",
        help="--ignore only filters files, not directories",
    )
    parser.add_argument(
        "--ignore-gitignore",
        action="store_true",
        help="Ignore .gitignore files and include everything",
    )
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        dest="ignore_patterns",
        help="fnmatch pattern to ignore (repeatable)",
    )
    parser.add_argument(
        "-o", "--output", help="Write output to a file instead of stdout"
    )
    parser.add_argument(
        "-c", "--cxml", action="store_true", dest="claude_xml", help="Claude XML output"
    )
    parser.add_argument(
        "-m",
        "--markdown",
        action="store_true",
        help="Output Markdown with fenced code blocks",
    )
    parser.add_argument(
        "-n", "--line-numbers", action="store_true", help="Add line numbers"
    )
    parser.add_argument(
        "-0",
        "--null",
        action="store_true",
        dest="use_null",
        help="Use NUL character as separator when reading paths from stdin",
    )
    args = parser.parse_args(argv)

    stdin_paths = read_paths_from_stdin(args.use_null)
    paths = [*args.paths, *stdin_paths]

    if args.output:
        fp = open(args.output, "w", encoding="utf-8")
        target = fp
    else:
        fp = None
        target = sys.stdout

    def writer(s):
        print(s, file=target)

    index = 1
    if args.claude_xml and paths:
        writer("<documents>")

    for path in paths:
        if not os.path.exists(path):
            parser.error(f"Path does not exist: {path}")
        inherited_rules = []
        if not args.ignore_gitignore:
            inherited_rules = read_gitignore(os.path.dirname(path))
        index = process_path(
            path,
            args.extensions,
            args.include_hidden,
            args.ignore_files_only,
            args.ignore_gitignore,
            inherited_rules,
            args.ignore_patterns,
            writer,
            args.claude_xml,
            args.markdown,
            args.line_numbers,
            index,
        )

    if args.claude_xml and paths:
        writer("</documents>")
    if fp:
        fp.close()
        print(f"Wrote snapshot to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()

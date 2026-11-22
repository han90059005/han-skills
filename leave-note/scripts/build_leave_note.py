#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成《家长知情同意书》（请假条）：改四项 -> 编译 PDF -> 出 300DPI JPG -> 复制到资料目录。

用法示例：
    python build_leave_note.py --leave 2026-10-27 --return 2026-10-29 --dest 上海 --sign 2026-10-26
    python build_leave_note.py --leave 2026年10月27日 --return 2026-10-29 --dest 上海 --no-copy

只依赖 Python 标准库 + 本机 xelatex（TeX Live）；JPG 优先用 PyMuPDF，缺失时回退 pdftoppm+Pillow。
"""
import argparse
import datetime as dt
import glob
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
TEMPLATE = os.path.join(SKILL, "assets", "template.tex")
SIG_FALLBACK = os.path.join(SKILL, "assets", "signature.jpg")
# 用户资料目录里放了最新签字图，优先用它，保证签名始终是最新那张
SIG_PREFERRED = os.path.join(r"I:\学习资料\0-个人资料\2-请假", "家长签名.jpg")
DEFAULT_COPY_DIR = r"I:\学习资料\0-个人资料\2-请假"
TEX_NAME = "家长知情同意书"
TECTONIC = r"D:\tectonic-0.17.0-x86_64-pc-windows-msvc\tectonic.exe"


# ---------------------------------------------------------------- 日期
def parse_date(raw, default_year=None):
    """接受 2026-10-27 / 2026.10.27 / 2026年10月27日 / 10-27（补当年）。"""
    s = raw.strip()
    s = s.replace("年", "-").replace("月", "-").replace("日", "")
    s = s.replace(".", "-").replace("/", "-").replace("—", "-")
    parts = [p for p in re.split(r"[-\s]+", s) if p]
    try:
        if len(parts) == 3:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        elif len(parts) == 2:
            y = default_year or dt.date.today().year
            m, d = int(parts[0]), int(parts[1])
        else:
            raise ValueError
        return dt.date(y, m, d)
    except ValueError:
        raise SystemExit(f"日期看不懂：{raw!r}（用 2026-10-27 或 2026年10月27日 这种写法）")


def fmt_dot(d):
    return f"{d.year}.{d.month}.{d.day}"


def fmt_cn(d):
    return f"{d.year}年{d.month}月{d.day}日"


# ---------------------------------------------------------------- 文案
def escape_tex(s):
    """地点可能含 & % # _ 等 LaTeX 特殊字符。"""
    out = []
    for ch in s:
        if ch in "&%$#_{}":
            out.append("\\" + ch)
        elif ch == "~":
            out.append("\\textasciitilde{}")
        elif ch == "^":
            out.append("\\textasciicircum{}")
        elif ch == "\\":
            out.append("\\textbackslash{}")
        else:
            out.append(ch)
    return "".join(out)


def render_tex(out_dir, leave, ret, dest, sign):
    with open(TEMPLATE, encoding="utf-8") as f:
        tex = f.read()
    repl = {
        "leavedate": fmt_dot(leave),
        "returndate": fmt_dot(ret),
        "destination": escape_tex(dest),
        "signdate": fmt_cn(sign),
    }
    for key, val in repl.items():
        pat = re.compile(r"(\\newcommand\{\\" + key + r"\})\{[^}]*\}")
        tex, n = pat.subn(lambda m: m.group(1) + "{" + val + "}", tex)
        if n != 1:
            raise SystemExit(f"模板里没找到 \\{key} 的定义，模板可能被改坏了")
    tex_path = os.path.join(out_dir, TEX_NAME + ".tex")
    with open(tex_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(tex)
    return tex_path


# ---------------------------------------------------------------- 编图
def copy_signature(out_dir):
    src = SIG_PREFERRED if os.path.isfile(SIG_PREFERRED) else SIG_FALLBACK
    if not os.path.isfile(src):
        raise SystemExit(f"找不到签名图：{SIG_PREFERRED} 和 {SIG_FALLBACK} 都不存在")
    dst = os.path.join(out_dir, "signature.jpg")
    shutil.copy2(src, dst)
    return src, dst


def find_xelatex():
    exe = shutil.which("xelatex")
    if exe:
        return exe
    for cand in (
        r"D:\AI-tools\latex\texlive\2026\bin\windows\xelatex.exe",
        r"C:\Program Files\MiKTeX\miktex\bin\x64\xelatex.exe",
    ):
        if os.path.isfile(cand):
            return cand
    return None


def compile_pdf(out_dir):
    tex = TEX_NAME + ".tex"
    pdf = os.path.join(out_dir, TEX_NAME + ".pdf")
    if os.path.isfile(pdf):
        os.remove(pdf)

    xelatex = find_xelatex()
    if xelatex:
        cmd = [xelatex, "-interaction=nonstopmode", "-halt-on-error", tex]
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        engine = "xelatex"
    elif os.path.isfile(TECTONIC):
        cmd = [TECTONIC, "-X", "compile", tex]
        env = os.environ.copy()
        for k in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
            env[k] = ""
        env["NO_PROXY"] = "*"
        env["no_proxy"] = "*"
        engine = "tectonic"
    else:
        raise SystemExit("本机既没有 xelatex 也没有 tectonic，无法编译")

    r = subprocess.run(
        cmd, cwd=out_dir, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0 or not os.path.isfile(pdf):
        print(r.stdout[-3000:], file=sys.stderr)
        raise SystemExit(f"{engine} 编译失败（返回码 {r.returncode}）")
    # 清理中间文件
    for ext in (".aux", ".log", ".out", ".toc"):
        p = os.path.join(out_dir, TEX_NAME + ext)
        if os.path.isfile(p):
            os.remove(p)
    return pdf, engine


def pdf_to_jpg(pdf, jpg, dpi=300, quality=92):
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf)
        pix = doc[0].get_pixmap(dpi=dpi)
        with open(jpg, "wb") as f:
            f.write(pix.tobytes("jpeg", jpg_quality=quality))
        return pix.width, pix.height, "pymupdf"
    except Exception:
        pass

    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm:
        prefix = os.path.join(os.path.dirname(jpg), "_pg")
        r = subprocess.run(
            [pdftoppm, "-png", "-r", str(dpi), "-singlefile", pdf, prefix],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        png = prefix + ".png"
        if r.returncode == 0 and os.path.isfile(png):
            try:
                from PIL import Image
                im = Image.open(png).convert("RGB")
                im.save(jpg, "JPEG", quality=quality, dpi=(dpi, dpi))
                size = im.size
                os.remove(png)
                return size[0], size[1], "pdftoppm"
            except Exception:
                if os.path.isfile(png):
                    os.remove(png)
    raise SystemExit("生成 JPG 失败：既没有 PyMuPDF，也没法用 pdftoppm + Pillow")


# ---------------------------------------------------------------- 交付
def copy_out(out_dir, target):
    copied, failed = [], []
    for ext in (".pdf", ".tex", ".jpg"):
        src = os.path.join(out_dir, TEX_NAME + ext)
        if not os.path.isfile(src):
            continue
        dst = os.path.join(target, TEX_NAME + ext)
        try:
            shutil.copy2(src, dst)
            copied.append(dst)
        except Exception as e:
            failed.append((dst, str(e)))
    return copied, failed


def main():
    ap = argparse.ArgumentParser(description="生成家长知情同意书 PDF + JPG")
    ap.add_argument("--leave", required=True, help="离开日期")
    ap.add_argument("--return", dest="ret", required=True, help="返校时间")
    ap.add_argument("--dest", required=True, help="前往地点")
    ap.add_argument("--sign", default=None, help="落款日期，默认今天")
    ap.add_argument("--out", default=None, help="输出目录，默认 <当前目录>/leave-note")
    ap.add_argument("--copy-dir", default=DEFAULT_COPY_DIR, help="复制目标目录")
    ap.add_argument("--no-copy", action="store_true", help="只生成，不复制到资料目录")
    args = ap.parse_args()

    today = dt.date.today()
    leave = parse_date(args.leave, today.year)
    ret = parse_date(args.ret, today.year)
    sign = parse_date(args.sign, today.year) if args.sign else today
    if ret < leave:
        raise SystemExit(f"返校时间 {fmt_dot(ret)} 早于离开日期 {fmt_dot(leave)}，先确认一下")

    out_dir = os.path.abspath(args.out or os.path.join(os.getcwd(), "leave-note"))
    os.makedirs(out_dir, exist_ok=True)

    tex = render_tex(out_dir, leave, ret, args.dest, sign)
    sig_src, _ = copy_signature(out_dir)
    pdf, engine = compile_pdf(out_dir)
    jpg = os.path.join(out_dir, TEX_NAME + ".jpg")
    w, h, jpg_engine = pdf_to_jpg(pdf, jpg)

    print(f"离开日期: {fmt_dot(leave)}")
    print(f"返校时间: {fmt_dot(ret)}")
    print(f"前往地点: {args.dest}")
    print(f"落款日期: {fmt_cn(sign)}")
    print(f"签名图  : {sig_src}")
    print(f"编译引擎: {engine}")
    print(f"TEX 生成: {tex}")
    print(f"PDF 生成: {pdf}")
    print(f"JPG 生成: {jpg} ({w}, {h}, {jpg_engine})")

    if not args.no_copy:
        copied, failed = copy_out(out_dir, args.copy_dir)
        for p in copied:
            print(f"复制到目录: {p}")
        for p, err in failed:
            print(f"复制失败: {p} -> {err}", file=sys.stderr)
            print("提示：目标文件可能正被 PDF 阅读器占用，关掉后重跑；或单独手动复制。", file=sys.stderr)


if __name__ == "__main__":
    main()

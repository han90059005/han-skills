# -*- coding: utf-8 -*-
"""Convert ASCII/Unicode sub/superscript notation to real LaTeX inside inline math."""
import re
import sys

GREEK = {
    "α": r"\alpha", "β": r"\beta", "γ": r"\gamma", "δ": r"\delta",
    "ε": r"\varepsilon", "ζ": r"\zeta", "η": r"\eta", "θ": r"\theta",
    "ι": r"\iota", "κ": r"\kappa", "λ": r"\lambda", "μ": r"\mu",
    "ν": r"\nu", "ξ": r"\xi", "π": r"\pi", "ρ": r"\rho", "σ": r"\sigma",
    "τ": r"\tau", "υ": r"\upsilon", "φ": r"\phi", "χ": r"\chi", "ψ": r"\psi",
    "ω": r"\omega", "Δ": r"\Delta", "Φ": r"\Phi", "Ω": r"\Omega",
    "Σ": r"\Sigma", "Ψ": r"\Psi",
}

TOKEN = re.compile(r"(?<![A-Za-z_\\])([A-Za-z]|[\u0391-\u03c9])((?:_[A-Za-z0-9]{1,6})+)")

SUP = str.maketrans({
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
    "⁻": "-", "⁺": "+", "ⁿ": "n",
})
SUB = str.maketrans({
    "₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4",
    "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9",
    "ₓ": "x",
})
SUP_RE = re.compile(r"(\d+(?:\.\d+)?)([⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺ⁿ]+)")
SUP_LET = re.compile(r"(?<![A-Za-z0-9])([A-Za-z])([⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺ⁿ]+)")
SUB_RE = re.compile(r"([A-Za-z])([₀₁₂₃₄₅₆₇₈₉ₓ]+)")

PROTECT = re.compile(r"(\$\$.*?\$\$|\$[^$]+\$|`[^`]+`)", re.S)


def sub_tex(part: str) -> str:
    if len(part) == 1:
        return "_{%s}" % part
    return "_{\\mathrm{%s}}" % part


def fix_token(m):
    base, subs = m.group(1), m.group(2)
    parts = subs.split("_")[1:]
    if base == "k" and parts == ["BT"]:
        return "$k_{\\mathrm{B}}T$"
    b = GREEK.get(base, base)
    body = "".join(sub_tex(p) for p in parts)
    return "$%s%s$" % (b, body)


def convert_text(t: str) -> str:
    t = t.replace("∬", "$\\iint$")
    t = TOKEN.sub(fix_token, t)
    t = SUP_RE.sub(lambda m: "$%s^{%s}$" % (m.group(1), m.group(2).translate(SUP)), t)
    t = SUP_LET.sub(lambda m: "$%s^{%s}$" % (GREEK.get(m.group(1), m.group(1)),
                                             m.group(2).translate(SUP)), t)
    t = SUB_RE.sub(lambda m: "$%s_{%s}$" % (GREEK.get(m.group(1), m.group(1)),
                                            m.group(2).translate(SUB)), t)
    return t


def process(src, dst, strip_fences=False):
    s = open(src, encoding="utf-8").read()
    if strip_fences:
        s = "\n".join(ln for ln in s.split("\n") if ln.strip() != "```")
    out = []
    for i, seg in enumerate(PROTECT.split(s)):
        out.append(seg if i % 2 else convert_text(seg))
    s2 = "".join(out)
    open(dst, "w", encoding="utf-8").write(s2)
    print("ok", dst)


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    strip = len(sys.argv) > 3 and sys.argv[3] == "strip"
    process(src, dst, strip)

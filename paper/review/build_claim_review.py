#!/usr/bin/env python3
"""Build an in-context old/new review PDF without editing the manuscript."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


PAPER = Path(__file__).resolve().parents[1]
ROOT = PAPER.parent

REVIEW_PREAMBLE = r"""
\usepackage{soul}
\usepackage{fancyhdr}
\definecolor{ReviewOld}{HTML}{FFD39A}
\definecolor{ReviewNew}{HTML}{FFF184}
\definecolor{ReviewInk}{HTML}{3F4855}
\soulregister\method0
\soulregister\citep7
\soulregister\citet7
\DeclareRobustCommand{\reviewchange}[3]{%
  \textsuperscript{\textcolor{ReviewInk}{\normalfont\scriptsize #1}}%
  {\sethlcolor{ReviewOld}\hl{#2}}%
  \space\allowbreak\ensuremath{\rightarrow}\space\allowbreak%
  {\sethlcolor{ReviewNew}\hl{#3}}%
}
\DeclareRobustCommand{\reviewadded}[1]{{\sethlcolor{ReviewNew}\hl{#1}}}
\pdfstringdefDisableCommands{\def\reviewchange#1#2#3{#3}\def\reviewadded#1{#1}}
\setlength{\headheight}{16pt}
\fancyhf{}
\fancyhead[L]{\normalfont\scriptsize REVIEW DRAFT: ITEM 1 - PROPOSED CHANGES}
\fancyhead[R]{\normalfont\scriptsize\colorbox{ReviewOld}{Old}\enspace$\rightarrow$\enspace\colorbox{ReviewNew}{New}}
\fancyfoot[C]{\normalfont\small\thepage}
\renewcommand{\headrulewidth}{0.3pt}
\pagestyle{fancy}
\raggedbottom
"""


def balanced(text):
    """Check braces in a selected LaTeX span, ignoring escaped braces."""
    level = 0
    for match in re.finditer(r"(?<!\\)[{}]", text):
        level += 1 if match[0] == "{" else -1
        if level < 0:
            return False
    return level == 0


def mark_text(old, new, number):
    """Keep common context and mark complete affected sentences where possible."""
    prefix = 0
    while prefix < min(len(old), len(new)) and old[prefix] == new[prefix]:
        prefix += 1
    while prefix and not old[prefix - 1].isspace():
        prefix -= 1

    suffix = 0
    while (suffix < min(len(old), len(new)) - prefix
           and old[-suffix - 1] == new[-suffix - 1]):
        suffix += 1
    while suffix and not old[len(old) - suffix - 1].isspace():
        suffix -= 1

    # Complete sentences read naturally after the arrow without needing to
    # mentally splice a shared subject back into the replacement.
    starts = [0] + [m.end() for m in re.finditer(r"[.!?]\s+", old[:prefix])]
    prefix = starts[-1]
    if suffix:
        stop = len(old) - suffix
        if not re.search(r"[.!?]\s*$", old[:stop]):
            ending = re.search(r"[.!?](?=\s|$)", old[stop:])
            suffix = len(old) - (stop + ending.end()) if ending else 0

    old_stop = len(old) - suffix
    new_stop = len(new) - suffix
    # Give additions a sentence of orange context rather than an empty old span.
    if not old[prefix:old_stop].strip():
        boundaries = list(re.finditer(r"[.!?]\s+", old[:prefix].rstrip()))
        prefix = boundaries[-1].end() if boundaries else 0

    before = old[prefix:old_stop]
    after = new[prefix:new_stop]
    if not balanced(before) or not balanced(after):
        prefix, suffix = 0, 0
        before, after = old, new

    # Explicit placeholders make a pure insertion/deletion arrow meaningful.
    old_mark = before.strip() or r"\textit{[no text]}"
    new_mark = after.strip() or r"\textit{[removed]}"
    old_mark = old_mark.replace(r"\method", "Eval-Pair Matrix")
    new_mark = new_mark.replace(r"\method", "Eval-Pair Matrix")
    # soul handles a nonbreaking space, but not TeX's explicit control-space.
    old_mark = old_mark.replace("\\ ", "~")
    new_mark = new_mark.replace("\\ ", "~")
    # Keep citations and cross-references atomic inside a highlighted run.
    old_mark = re.sub(r"(\\(?:cite[pt]|ref|pageref)\{[^}]*\})", r"\\mbox{\1}", old_mark)
    new_mark = re.sub(r"(\\(?:cite[pt]|ref|pageref)\{[^}]*\})", r"\\mbox{\1}", new_mark)
    marked = rf"\reviewchange{{{number}}}{{{old_mark}}}{{{new_mark}}}"
    left = old[:prefix]
    right = old[len(old) - suffix:] if suffix else ""
    if right and not right[0].isspace():
        marked += " "
    return left + marked + right


def mark_line(change):
    old, new = change["old"], change["new"]
    if "addition" in change:
        if new != old + change["addition"]:
            raise SystemExit(f"Addition does not match change {change['change']}")
        return old + mark_addition(change["addition"], change["change"])
    if change.get("segments"):
        marked = old
        expected = old
        for segment in change["segments"]:
            if expected.count(segment["old"]) != 1:
                raise SystemExit(f"Ambiguous segment in change {change['change']}")
            expected = expected.replace(segment["old"], segment["new"], 1)
            marked = marked.replace(segment["old"], mark_text(
                segment["old"], segment["new"], change["change"]), 1)
        if expected != new:
            raise SystemExit(f"Segments do not match change {change['change']}")
        return marked
    # Keep structural commands outside soul highlighting (including captions).
    wrapper = r"^(\s*\\(?:paragraph|subsection|caption|captionof\{[^}]+\})\{)(.*)(\})$"
    a, b = re.match(wrapper, old), re.match(wrapper, new)
    if a and b and a[1] == b[1]:
        return a[1] + mark_text(a[2], b[2], change["change"]) + a[3]
    # A list item's label stays unhighlighted; the proposed wording follows it.
    wrapper = r"^(\s*\\item\s+\\textbf\{[^}]+\}\s*)(.*)$"
    a, b = re.match(wrapper, old), re.match(wrapper, new)
    if a and b and a[1] == b[1]:
        return a[1] + mark_text(a[2], b[2], change["change"])
    return mark_text(old, new, change["change"])


def mark_addition(addition, number):
    """Mark a new paragraph/table block, preserving its LaTeX structure."""
    def yellow(text):
        text = re.sub(r"(\\(?:ref|pageref)\{[^}]*\})", r"\\mbox{\1}", text)
        return r"\reviewadded{" + text + "}"

    marked = ["", "", rf"\noindent\textsuperscript{{{number}}}"
              r"{\sethlcolor{ReviewOld}\hl{\textit{[no text]}}}"
              r"\enspace$\rightarrow$\par"]
    for line in addition.strip().splitlines():
        wrapper = re.fullmatch(r"(\\(?:paragraph|subsection|caption)\{)(.*)(\})", line)
        if wrapper:
            marked.append(wrapper[1] + yellow(wrapper[2]) + wrapper[3])
        elif " & " in line and line.endswith(r"\\"):
            marked.append(" & ".join(yellow(cell.strip()) for cell in line[:-2].split("&")) + r" \\")
        elif (not line.strip() or re.match(
                r"^\\(?:begin|end|label|centering|scriptsize|small|toprule|midrule|bottomrule|renewcommand)\b", line)):
            marked.append(line)
        else:
            marked.append(yellow(line))
    return "\n".join(marked) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--changes", default="central_claim_changes.json",
                        help="Proposal JSON filename in paper/review")
    parser.add_argument("--item", type=int, default=1)
    parser.add_argument("--name", default="claim", help="Output filename stem")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]+", args.name):
        parser.error("--name must contain only lowercase letters, digits, and hyphens")
    BUILD = ROOT / f"tmp/pdfs/{args.name}-review"
    OUTPUT = ROOT / f"output/pdf/eval-pair-matrix-{args.name}-review.pdf"
    CHANGES = json.loads((PAPER / "review" / args.changes).read_text())
    BUILD.mkdir(parents=True, exist_ok=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    for name in ("main_body.tex", "appendix_content.tex"):
        lines = (PAPER / name).read_text().splitlines()
        for change in (c for c in CHANGES if c["file"] == name):
            index = change["line"] - 1
            if lines[index] != change["old"]:
                raise SystemExit(f"Baseline changed at {name}:{index + 1}; review the proposal first")
            lines[index] = mark_line(change)
        (BUILD / name.replace(".tex", "_review.tex")).write_text("\n".join(lines) + "\n")

    wrapper = (PAPER / "camera_ready.tex").read_text()
    preamble = REVIEW_PREAMBLE.replace("ITEM 1", f"ITEM {args.item}")
    wrapper = wrapper.replace(r"\begin{document}", preamble + "\n" + r"\begin{document}")
    wrapper = wrapper.replace(r"\input{main_body}", r"\input{main_body_review}")
    wrapper = wrapper.replace(r"\input{appendix_content}", r"\input{appendix_content_review}")
    wrapper = wrapper.replace(r"\maketitle", r"\maketitle\thispagestyle{fancy}")
    (BUILD / "claim_review.tex").write_text(wrapper)
    env = dict(os.environ)
    env["TEXINPUTS"] = str(BUILD) + os.pathsep + env.get("TEXINPUTS", "")
    for number in range(1, 4):
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error",
             f"-output-directory={BUILD}", str(BUILD / "claim_review.tex")],
            cwd=PAPER, env=env, capture_output=True, text=True,
        )
        (BUILD / f"build-pass-{number}.txt").write_text(result.stdout + result.stderr)
        if result.returncode:
            raise SystemExit("\n".join((result.stdout + result.stderr).splitlines()[-65:]))
    shutil.copy2(BUILD / "claim_review.pdf", OUTPUT)
    print(f"Built {OUTPUT}")


if __name__ == "__main__":
    main()

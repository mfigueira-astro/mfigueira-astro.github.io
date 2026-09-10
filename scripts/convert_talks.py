#!/usr/bin/env python3
"""
Convert a LaTeX CV "Conferences and Seminars" section (\\subsection{...} +
\\cvitem{year}{\\textit{Title\\newline} Venue details}) into the Talks/Seminars
page and write it directly into your Jekyll repo.

Usage (run from repo root):
    python3 scripts/convert_talks.py talks.tex

Writes _pages/talks.md, grouped by category (Contributed talks, Posters,
Seminars, Short talks, ...) matching your LaTeX \\subsection headers, then
sorted by year (descending) within each category.
"""

import argparse
import re
import sys
from pathlib import Path

ACCENTS = {
    "a": "\u00e1", "e": "\u00e9", "i": "\u00ed", "o": "\u00f3", "u": "\u00fa",
    "n": "\u0144", "c": "\u0107", "s": "\u015b", "z": "\u017a",
    "A": "\u00c1", "E": "\u00c9", "I": "\u00cd", "O": "\u00d3", "U": "\u00da",
    "N": "\u0143", "C": "\u0106", "S": "\u015a", "Z": "\u0179",
}


def find_balanced(text, start):
    """Given text[start] == '{', return (inner_text, index_after_closing_brace)."""
    assert text[start] == "{"
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
    raise ValueError("Unbalanced braces starting at %d" % start)


def clean_latex(text):
    text = text.replace("\\newline", " ")
    # accented characters: \'{o} -> \u00f3, etc.
    text = re.sub(
        r"\\'\{(\w)\}", lambda m: ACCENTS.get(m.group(1), m.group(1)), text
    )
    text = re.sub(r"\\~\{(\w)\}", lambda m: m.group(1), text)
    # Polish l/L with stroke (\l, \L) -- must run before the generic
    # bare-command stripper below, or the letter would just vanish
    text = re.sub(r"\\l\b", "\u0142", text)
    text = re.sub(r"\\L\b", "\u0141", text)
    text = text.replace("\\sim", "~")
    text = text.replace("\\&", "&")
    text = text.replace("~", " ")
    # strip $...$ math mode delimiters, keep contents
    text = re.sub(r"\$([^$]*)\$", r"\1", text)
    # math-mode superscripts like ^{st} -> st
    text = re.sub(r"\^\{([^{}]*)\}", r"\1", text)
    # repeatedly unwrap \textit{...}, \textsc{...}, \textrm{...}, \textbf{...}
    # (innermost first, since content has no braces left after a pass)
    pattern = re.compile(r"\\text(it|sc|rm|bf)\{([^{}]*)\}")
    prev = None
    while prev != text:
        prev = text
        text = pattern.sub(lambda m: m.group(2), text)
    # drop any remaining bare commands with no args (e.g. \hrulefill)
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    # any leftover stray (non-command) braces at this point are decorative
    # grouping only -- drop the brace characters but keep their contents
    text = text.replace("{", "").replace("}", "")
    # collapse whitespace, strip stray leading commas/spaces
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^,\s*", "", text)
    return text


def parse_entries(text):
    entries = []
    # map each character position to the category active at that point
    subsection_positions = [
        (m.start(), clean_latex(m.group(1)))
        for m in re.finditer(r"\\subsection\{([^{}]*)\}", text)
    ]

    def category_for(pos):
        cat = "Talks"
        for spos, sname in subsection_positions:
            if spos <= pos:
                cat = sname
            else:
                break
        return cat

    for m in re.finditer(r"\\cvitem\{", text):
        year_start = m.end() - 1
        year, after_year = find_balanced(text, year_start)
        # after_year should point right at the '{' of the content block
        if after_year >= len(text) or text[after_year] != "{":
            continue
        content, after_content = find_balanced(text, after_year)

        # find the first \textit{...} in content -> becomes the title
        tmatch = re.search(r"\\textit\{", content)
        if tmatch:
            title_raw, after_title = find_balanced(content, tmatch.end() - 1)
            title = clean_latex(title_raw)
            venue = clean_latex(content[after_title:])
        else:
            title = clean_latex(content)
            venue = ""

        entries.append(
            {
                "year": year.strip(),
                "category": category_for(m.start()),
                "title": title,
                "venue": venue,
            }
        )
    return entries


def sort_key(entry):
    # sort by the first 4-digit year found, descending
    m = re.search(r"\d{4}", entry["year"])
    return -(int(m.group(0)) if m else 0)


CATEGORY_ORDER = ["Seminars", "Contributed talks", "Short talks", "Posters"]


def render_body(entries):
    by_category = {}
    for e in entries:
        by_category.setdefault(e["category"], []).append(e)

    # fixed display order first; any category not in the list (e.g. a new
    # \subsection you add later) falls back to appearing after those, in
    # the order it was first encountered
    order = [c for c in CATEGORY_ORDER if c in by_category]
    order += [c for c in by_category if c not in order]

    total = len(entries)
    years = [int(re.search(r"\d{4}", e["year"]).group(0)) for e in entries if re.search(r"\d{4}", e["year"])]
    year_range = f"{min(years)}\u2013{max(years)}" if years else ""
    out = [f'<p class="proposals-summary">{total} talks/seminars ({year_range}).</p>\n']

    for cat in order:
        out.append(f"<h2>{cat}</h2>\n")
        for e in sorted(by_category[cat], key=sort_key):
            out.append('<div class="card mt-3 p-3">')
            out.append(f'  <div class="prop-title">{e["title"]}</div>')
            if e["venue"]:
                out.append(f'  <div class="periodical">{e["venue"]}</div>')
            out.append(f'  <div class="periodical">{e["year"]}</div>')
            out.append("</div>\n")
    return "\n".join(out)


def page_header():
    return """---
layout: page
title: Talks / Seminars
permalink: /talks/
nav: true
nav_order: 6
description:
---

<div class="publications">

"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    output_path = Path(args.output) if args.output else repo_root / "../_pages" / "talks.md"

    text = Path(args.input).read_text(encoding="utf-8")
    entries = parse_entries(text)
    if not entries:
        print("No \\cvitem{...}{...} entries found.", file=sys.stderr)
        sys.exit(1)

    page_content = page_header() + render_body(entries) + "\n</div>\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(page_content, encoding="utf-8")
    print(f"Wrote {len(entries)} entries across {len(set(e['category'] for e in entries))} categories to {output_path}")


if __name__ == "__main__":
    main()

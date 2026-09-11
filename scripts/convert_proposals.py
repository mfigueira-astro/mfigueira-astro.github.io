#!/usr/bin/env python3
"""
Convert moderncv \\cvitem{year}{...} observing-proposal entries into
the Observing Proposals page and write it straight into your Jekyll repo.

Usage (run from your repo's root folder):
    python3 scripts/convert_proposals.py new_proposals.tex

Input format, one entry per line:
    \\cvitem{2026}{\\textbf{APEX: }Title (PI: Name)}

Optional: attach a related paper link by adding a comment line right
after a \\cvitem entry:
    \\cvitem{2023}{\\textbf{APEX: }Some proposal (PI: You)}
    % paper: https://doi.org/10.1051/0004-6361/202346396

This will:
  1. Parse every entry (plus any attached "% paper:" link).
  2. Sort entries within each year alphabetically by title.
  3. Write the full page to _pages/observing-proposals.md (overwriting it),
     including a one-line summary and colored telescope badges.
  4. Make sure the .prop-title CSS rule exists in assets/css/main.scss,
     appending it if missing.
  5. Create _data/telescopes.yml (telescope -> badge color) if it doesn't
     exist yet, WITHOUT overwriting it if it does -- so you can freely
     add new telescopes or tweak colors there without losing edits.
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path
import os

CVITEM_RE = re.compile(
    r"\\cvitem\{(?P<year>\d{4})\}\{"
    r"\\textbf\{(?P<telescope>[^:]+):\s*\}"
    r"(?P<rest>.*)"
    r"\}\s*$"
)

PI_RE = re.compile(r"\((?P<label>PIs?):\s*(?P<names>.*?)\)\s*$")
PAPER_RE = re.compile(r"^%\s*paper:\s*(?P<url>\S+)\s*$")

PAGE_FOOTER = "\n</div>\n"

PROP_TITLE_CSS = """
.prop-title {
  font-weight: 600;
}

.prop-title .badge {
  font-size: 0.75rem;
  vertical-align: middle;
  margin-left: 0.5rem;
}
"""

DEFAULT_TELESCOPE_COLORS = """"APEX":
  color: "#c0392b"
"IRAM-30M":
  color: "#2980b9"
"ALMA":
  color: "#27ae60"
"NOEMA":
  color: "#8e44ad"
"JCMT":
  color: "#d35400"
"""


def clean_title(title: str) -> str:
    return title.strip().replace('"', "").strip()


def parse_entries(text: str):
    entries = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line or "\\cvitem" not in line:
            continue
        match = CVITEM_RE.match(line)
        if not match:
            print(f"Warning: could not parse line: {line}", file=sys.stderr)
            continue
        year = match.group("year")
        telescope = match.group("telescope").strip()
        rest = match.group("rest").strip()

        pi_match = PI_RE.search(rest)
        if pi_match:
            pi_label = pi_match.group("label")
            pi_names = pi_match.group("names").strip()
            title = rest[: pi_match.start()].strip()
        else:
            pi_label, pi_names = "PI", ""
            title = rest

        # Check whether the following lines are one or more
        # "% paper: URL" tags (any number, immediately after the entry)
        paper_urls = []
        while i < len(lines):
            next_line = lines[i].strip()
            paper_match = PAPER_RE.match(next_line)
            if not paper_match:
                break
            paper_urls.append(paper_match.group("url"))
            i += 1

        entries.append(
            {
                "year": year,
                "telescope": telescope,
                "title": clean_title(title),
                "pi_label": pi_label,
                "pi_names": pi_names,
                "paper_urls": paper_urls,
            }
        )
    return entries


def render_summary(entries) -> str:
    years = sorted({e["year"] for e in entries})
    telescopes = sorted({e["telescope"] for e in entries})
    year_range = years[0] if len(years) == 1 else f"{years[0]}\u2013{years[-1]}"

    if len(telescopes) == 1:
        tel_text = telescopes[0]
    elif len(telescopes) == 2:
        tel_text = f"{telescopes[0]} and {telescopes[1]}"
    else:
        tel_text = ", ".join(telescopes[:-1]) + f", and {telescopes[-1]}"

    count = len(entries)
    plural = "proposal" if count == 1 else "proposals"
    return f'<p class="proposals-summary">{count} {plural} ({year_range}) across {tel_text}.</p>\n'


def render_body(entries) -> str:
    by_year = defaultdict(list)
    for e in entries:
        by_year[e["year"]].append(e)

    out = [render_summary(entries)]
    for year in sorted(by_year.keys(), reverse=True):
        out.append(f"<h2>{year}</h2>\n")
        year_entries = sorted(by_year[year], key=lambda e: e["title"].lower())
        for e in year_entries:
            out.append('<div class="card mt-3 p-3">')
            out.append(
                '  <div class="prop-title">'
                f'{e["title"]}'
                " "
                "{% assign _tel = \"" + e["telescope"] + "\" %}"
                "{% if site.data.telescopes[_tel] %}"
                '<abbr class="badge" style="background-color:{{ site.data.telescopes[_tel].color }}">'
                "{{ _tel }}</abbr>"
                "{% else %}"
                '<abbr class="badge">' + e["telescope"] + "</abbr>"
                "{% endif %}"
                "</div>"
            )
            out.append(f'  <div class="periodical">{e["pi_label"]}: {e["pi_names"]}</div>')
            if e["paper_urls"]:
                if len(e["paper_urls"]) == 1:
                    out.append(
                        f'  <div class="periodical"><a href="{e["paper_urls"][0]}">'
                        "\u2192 Related paper</a></div>"
                    )
                else:
                    links = ", ".join(
                        f'<a href="{url}">{i}</a>' for i, url in enumerate(e["paper_urls"], start=1)
                    )
                    out.append(f'  <div class="periodical">Related papers: {links}</div>')
            out.append("</div>\n")
    return "\n".join(out)


def page_header() -> str:
    return """---
layout: page
title: Observing Proposals
permalink: /observing-proposals/
nav: true
nav_order: 5
description:
---

<div class="publications">

"""


def ensure_css(css_path: Path):
    if not css_path.exists():
        print(f"Warning: {css_path} not found, skipping CSS update.", file=sys.stderr)
        return
    content = css_path.read_text(encoding="utf-8")
    if ".prop-title" in content:
        return
    with css_path.open("a", encoding="utf-8") as f:
        f.write(PROP_TITLE_CSS)
    print(f"Added .prop-title rule to {css_path}")


def ensure_telescopes_data(data_path: Path):
    if data_path.exists():
        return  # never overwrite -- this file is meant to be hand-edited
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(DEFAULT_TELESCOPE_COLORS, encoding="utf-8")
    print(f"Created {data_path} with default telescope colors")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Path to a .tex file containing \\cvitem lines")
    parser.add_argument("--repo-root", default=".", help="Repo root (default: current directory)")
    parser.add_argument("--output", default=None, help="Override output page path")
    parser.add_argument("--css", default=None, help="Override main.scss path")
    parser.add_argument("--telescopes-data", default=None, help="Override _data/telescopes.yml path")
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    output_path = Path(args.output) if args.output else repo_root / "mfigueira-astro.github.io/_pages" / "observing-proposals.md"
    os.system("pwd")
    css_path = Path(args.css) if args.css else repo_root / "mfigueira-astro.github.io/assets" / "css" / "main.scss"
    telescopes_path = (
        Path(args.telescopes_data) if args.telescopes_data else repo_root / "mfigueira-astro.github.io/_data" / "telescopes.yml"
    )

    text = Path(args.input).read_text(encoding="utf-8")
    entries = parse_entries(text)
    if not entries:
        print("No \\cvitem{...}{...} entries found.", file=sys.stderr)
        sys.exit(1)

    page_content = page_header() + render_body(entries) + PAGE_FOOTER

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(page_content, encoding="utf-8")
    print(f"Wrote {len(entries)} entries to {output_path}")

    ensure_css(css_path)
    ensure_telescopes_data(telescopes_path)


if __name__ == "__main__":
    main()

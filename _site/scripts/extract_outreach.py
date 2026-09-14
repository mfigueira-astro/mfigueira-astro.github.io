#!/usr/bin/env python3
"""
Extract the \\section{Outreach} block from a CV .tex file (moderncv-style,
using \\cvitem{year}{content}) and generate an al-folio _pages/outreach.md
page using the .card / .publications layout already used on the site.

Usage:
    python3 extract_outreach.py main.tex > outreach.md
    python3 extract_outreach.py main.tex -o /path/to/outreach.md
"""

import re
import sys
import argparse
import unicodedata


# --- Polish LaTeX escape sequences -> UTF-8 -------------------------------
# moderncv/polski.sty style escapes seen in this file: \k{a}, \.z, \'s,
# \c e, \l  (ogonek, kropka, acute, cedilla, l-stroke)
POLISH_MAP = [
    (r"\\k\{a\}", "ą"), (r"\\k\{e\}", "ę"), (r"\\k\s?a", "ą"), (r"\\k\s?e", "ę"),
    (r"\\c\s?e", "ę"), (r"\\c\s?a", "ą"),
    (r"\\\.z", "ż"), (r"\\\.Z", "Ż"),
    (r"\\'s", "ś"), (r"\\'S", "Ś"),
    (r"\\'n", "ń"), (r"\\'N", "Ń"),
    (r"\\'c", "ć"), (r"\\'C", "Ć"),
    (r"\\'z", "ź"), (r"\\'Z", "Ź"),
    (r"\{\\l\}", "ł"), (r"\\l\b", "ł"), (r"\{\\L\}", "Ł"), (r"\\L\b", "Ł"),
]


def find_balanced(text, start):
    """Given text[start] == '{', return the index just after its matching '}'."""
    assert text[start] == "{"
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    raise ValueError("Unbalanced braces")


def extract_section(tex, name):
    """Return the raw text of \\section{...name...} up to the next \\section."""
    pattern = re.compile(r"\\section\{[^}]*" + re.escape(name) + r"[^}]*\}")
    m = pattern.search(tex)
    if not m:
        raise ValueError(f"Section '{name}' not found")
    start = m.end()
    next_section = re.search(r"\\section\{", tex[start:])
    end = start + next_section.start() if next_section else len(tex)
    return tex[start:end]


def extract_cvitems(section_text):
    """Yield (year, content) for each \\cvitem{year}{content} in the section."""
    items = []
    for m in re.finditer(r"\\cvitem\{", section_text):
        year_start = m.end() - 1
        year_end = find_balanced(section_text, year_start)
        year = section_text[year_start + 1:year_end - 1].strip()

        content_start = year_end
        if content_start >= len(section_text) or section_text[content_start] != "{":
            continue
        content_end = find_balanced(section_text, content_start)
        content = section_text[content_start + 1:content_end - 1].strip()

        items.append((year, content))
    return items


CMD_WRAPPERS = {
    "textbf": ("<strong>", "</strong>"),
    "textit": ("<em>", "</em>"),
    "emph": ("<em>", "</em>"),
    "textsc": ('<span style="font-variant: small-caps;">', "</span>"),
}


def latex_to_html(s):
    """Best-effort, brace-aware conversion of LaTeX used inside \\cvitem content.

    Walks the string left to right so that arbitrarily nested {…} groups
    (e.g. \\href{url}{Title with {\\l} and {II} inside}) are handled
    correctly, unlike a single-pass regex.
    """
    # Polish diacritics first (raw backslash escapes, not brace commands)
    for pat, repl in POLISH_MAP:
        s = re.sub(pat, repl, s)

    out = []
    i = 0
    n = len(s)
    while i < n:
        if s[i] == "\\":
            m = re.match(r"\\([a-zA-Z]+)", s[i:])
            if m:
                cmd = m.group(1)
                j = i + m.end()  # index right after the command name
                # skip whitespace between command and its first '{'
                k = j
                while k < n and s[k] in " \t":
                    k += 1

                if cmd == "href" and k < n and s[k] == "{":
                    url_end = find_balanced(s, k)
                    url = s[k + 1:url_end - 1]
                    k2 = url_end
                    if k2 < n and s[k2] == "{":
                        text_end = find_balanced(s, k2)
                        text = s[k2 + 1:text_end - 1]
                        out.append(f'<a href="{url}">{latex_to_html(text)}</a>')
                        i = text_end
                        continue
                elif cmd in CMD_WRAPPERS and k < n and s[k] == "{":
                    arg_end = find_balanced(s, k)
                    arg = s[k + 1:arg_end - 1]
                    open_tag, close_tag = CMD_WRAPPERS[cmd]
                    out.append(f"{open_tag}{latex_to_html(arg)}{close_tag}")
                    i = arg_end
                    continue
                elif cmd == "newline":
                    out.append(" — ")
                    i = j
                    continue
                else:
                    # Unknown command: drop the backslash+name, keep any
                    # following {..} group's contents (common LaTeX pattern)
                    if k < n and s[k] == "{":
                        arg_end = find_balanced(s, k)
                        out.append(latex_to_html(s[k + 1:arg_end - 1]))
                        i = arg_end
                        continue
                    i = j
                    continue
            i += 1
            continue
        elif s[i] == "{":
            end = find_balanced(s, i)
            out.append(latex_to_html(s[i + 1:end - 1]))
            i = end
            continue
        else:
            out.append(s[i])
            i += 1

    result = "".join(out)
    result = re.sub(r"\s+", " ", result).strip()
    return result


def split_title_venue(html):
    """Split '<strong>Title</strong> (...) — Venue, Date' into (title_html, venue_html)."""
    if " — " in html:
        title, venue = html.split(" — ", 1)
        return title.strip(), venue.strip()
    return html.strip(), ""


def classify(content_raw):
    """Heuristic: entries with a \\href are published articles; otherwise talks."""
    return "Popular Science Articles" if "\\href" in content_raw else "Talks"


def build_page(items, title="Outreach", permalink="/outreach/",
                nav_order=6, description="Popular science writing and public engagement."):
    groups = {}
    for year, content_raw in items:
        group = classify(content_raw)
        html = latex_to_html(content_raw)
        title_html, venue_html = split_title_venue(html)
        groups.setdefault(group, []).append((year, title_html, venue_html))

    lines = []
    lines.append("---")
    lines.append("layout: page")
    lines.append(f"title: {title}")
    lines.append(f"permalink: {permalink}")
    lines.append("nav: true")
    lines.append(f"nav_order: {nav_order}")
    lines.append(f"description: {description}")
    lines.append("---")
    lines.append("")
    lines.append('<div class="publications">')
    lines.append("")

    # Preserve original document order of first appearance for group headings
    seen_order = []
    for year, content_raw in items:
        g = classify(content_raw)
        if g not in seen_order:
            seen_order.append(g)

    for group in seen_order:
        lines.append(f"<h2>{group}</h2>")
        lines.append("")
        lines.append('<ol class="bibliography">')
        for year, title_html, venue_html in groups[group]:
            lines.append("<li>")
            lines.append(f'  <div class="title">{title_html}</div>')
            if venue_html:
                lines.append(f'  <div class="periodical">{venue_html}</div>')
            lines.append("</li>")
        lines.append("</ol>")
        lines.append("")

    lines.append("</div>")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tex_file", help="Path to main.tex")
    parser.add_argument("-o", "--output", help="Output path (default: stdout)")
    parser.add_argument("--section", default="Outreach", help="Section name to extract")
    args = parser.parse_args()

    with open(args.tex_file, encoding="utf-8") as f:
        tex = f.read()

    section_text = extract_section(tex, args.section)
    items = extract_cvitems(section_text)

    if not items:
        sys.exit(f"No \\cvitem entries found in section '{args.section}'")

    page = build_page(items)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(page)
        print(f"Wrote {len(items)} entries to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(page)


if __name__ == "__main__":
    main()

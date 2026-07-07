#!/usr/bin/env python3
"""
Deep PDF parser for academic papers.
Extracts text, sections, metadata, figures, tables, and equations.
Handles two-column layout ordering.

Usage:
  python parse_pdf.py --pdf paper.pdf
  python parse_pdf.py --pdf paper.pdf --pages 3-5
  python parse_pdf.py --pdf paper.pdf --sections "Methodology"
  python parse_pdf.py --pdf paper.pdf --output json
"""

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from _bootstrap import ensure_venv

ensure_venv(__file__)

from pypdf import PdfReader


# --- Section detection patterns ---
SECTION_PATTERNS = [
    re.compile(r"^\s*Abstract\s*$", re.IGNORECASE),
    re.compile(
        r"^\s*\d+[\.\s]+(?:Introduction|Related\s+Work|Background)\b", re.IGNORECASE
    ),
    re.compile(
        r"^\s*\d+[\.\s]+(?:Method|Methods|Methodology|Approach|Architecture|"
        r"Model|Proposed|Our\s+(?:Approach|Method|Model|Framework))",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*\d+[\.\s]+(?:Experiment|Experiments|Evaluation|Results|"
        r"Implementation|Training|Inference)",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*\d+[\.\s]+(?:Discussion|Analysis|Ablation|Case\s+Study|"
        r"Qualitative|Quantitative)",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*\d+[\.\s]+(?:Conclusion|Conclusions|Future\s+Work|"
        r"Summary|Limitations)",
        re.IGNORECASE,
    ),
    re.compile(r"^\s*References\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d+[\.\s]+([A-Z][\w\s\-]{3,})\s*$"),
]

FIGURE_RE = re.compile(r"(?:Fig(?:ure)?\.?\s*(\d+))", re.IGNORECASE)
TABLE_RE = re.compile(r"(?:Table\.?\s*(\d+))", re.IGNORECASE)
EQUATION_RE = re.compile(r"(?:Eq(?:uation)?\s*\(?\s*(\d+)\s*\)?)", re.IGNORECASE)


@dataclass
class TextItem:
    text: str
    page: int
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass
class Section:
    title: str
    page: int
    start_line: int
    end_line: int
    text: str


@dataclass
class PaperData:
    metadata: dict = field(default_factory=dict)
    full_text: str = ""
    text_per_page: dict = field(default_factory=dict)
    sections: list = field(default_factory=list)
    figures: list = field(default_factory=list)
    tables: list = field(default_factory=list)
    equations: list = field(default_factory=list)


# --- Visitor for positional text extraction ---


class _TextVisitor:
    def __init__(self):
        self.items = []

    def visitor_text(self, text, user_matrix, tm_matrix, font_dict, font_size):
        stripped = text.strip()
        if stripped:
            self.items.append(
                TextItem(
                    text=stripped,
                    page=0,
                    x0=tm_matrix[4],
                    y0=tm_matrix[5],
                    x1=tm_matrix[4] + abs(tm_matrix[0]) * len(text),
                    y1=tm_matrix[5] + tm_matrix[3],
                )
            )


def extract_text_items(reader, pages_set):
    items = []
    for page_num in sorted(pages_set):
        if page_num < 1 or page_num > len(reader.pages):
            continue
        page = reader.pages[page_num - 1]
        try:
            visitor = _TextVisitor()
            page.extract_text(visitor_text=visitor)
            for item in visitor.items:
                item.page = page_num
                items.append(item)
        except Exception:
            text = page.extract_text()
            if text:
                for line in text.split("\n"):
                    stripped = line.strip()
                    if stripped:
                        items.append(
                            TextItem(
                                text=stripped,
                                page=page_num,
                                x0=0,
                                y0=0,
                                x1=0,
                                y1=0,
                            )
                        )
    return items


# --- Column ordering ---


def order_two_columns(items):
    if not items:
        return items

    page_groups = {}
    for item in items:
        page_groups.setdefault(item.page, []).append(item)

    ordered = []
    for page_num in sorted(page_groups.keys()):
        page_items = page_groups[page_num]

        if not page_items:
            continue

        xs = [i.x0 for i in page_items if i.x0 > 0]
        if not xs:
            ordered.extend(page_items)
            continue

        page_width = max(i.x1 for i in page_items if i.x1 > 0)
        if page_width < 100:
            ordered.extend(page_items)
            continue

        mid_x = page_width / 2
        left = [i for i in page_items if i.x1 > 0 and i.x1 <= mid_x]
        right = [i for i in page_items if i.x0 > 0 and i.x0 >= mid_x]

        if not left or not right:
            ordered.extend(sorted(page_items, key=lambda i: (i.y0, i.x0), reverse=True))
            continue

        left.sort(key=lambda i: i.y0, reverse=True)
        right.sort(key=lambda i: i.y0, reverse=True)

        while left and right:
            if left[-1].y0 >= right[-1].y0:
                ordered.append(left.pop())
            else:
                ordered.append(right.pop())
        ordered.extend(reversed(left))
        ordered.extend(reversed(right))

    return ordered


# --- Section detection ---


def is_section_header(text):
    for pattern in SECTION_PATTERNS:
        if pattern.match(text):
            return True
    return False


def detect_sections(items):
    if not items:
        return []

    sections = []
    current_title = None
    current_start = 0
    current_page = items[0].page

    for i, item in enumerate(items):
        if is_section_header(item.text):
            if current_title is not None and i > current_start:
                section_text = " ".join(it.text for it in items[current_start:i])
                sections.append(
                    Section(
                        title=current_title,
                        page=current_page,
                        start_line=current_start,
                        end_line=i - 1,
                        text=section_text,
                    )
                )
            current_title = item.text.strip()
            current_start = i
            current_page = item.page

    if current_title is not None and current_start < len(items):
        section_text = " ".join(it.text for it in items[current_start:])
        sections.append(
            Section(
                title=current_title,
                page=current_page,
                start_line=current_start,
                end_line=len(items) - 1,
                text=section_text,
            )
        )

    return sections


# --- Figure / Table / Equation detection ---


def detect_figures_tables(text):
    figures = []
    tables = []
    for m in FIGURE_RE.finditer(text):
        figures.append({"number": int(m.group(1)), "position": m.start()})
    for m in TABLE_RE.finditer(text):
        tables.append({"number": int(m.group(1)), "position": m.start()})
    return figures, tables


def detect_equations(text):
    seen = set()
    equations = []
    for m in EQUATION_RE.finditer(text):
        num = m.group(1)
        if num not in seen:
            seen.add(num)
            equations.append({"number": int(num), "position": m.start()})
    return equations


# --- Metadata ---


def extract_metadata(reader):
    meta = {}
    pdf_meta = reader.metadata or {}
    for key in ("/Title", "/Author", "/Creator", "/Producer", "/Subject"):
        val = pdf_meta.get(key, "")
        if val:
            meta[key.lstrip("/").lower()] = str(val).strip()

    first_text = ""
    if reader.pages:
        try:
            first_text = reader.pages[0].extract_text() or ""
        except Exception:
            pass

    doi_m = re.search(r"(?:doi|DOI)[:\s]*(10\.\d{4,}/[^\s]+)", first_text)
    if doi_m:
        meta["doi"] = doi_m.group(1)

    year_m = re.search(r"(?:19|20)\d{2}", first_text[:500])
    if year_m:
        meta["year"] = int(year_m.group(0))

    if not meta.get("title"):
        title_lines = []
        for line in first_text.split("\n")[:15]:
            stripped = line.strip()
            if len(stripped) > 10:
                title_lines.append(stripped)
            if len(title_lines) >= 3:
                break
        if title_lines:
            meta["extracted_title"] = " ".join(title_lines[:3])

    return meta


# --- Page range parsing ---


def parse_page_range(raw, total):
    if not raw:
        return set(range(1, total + 1))
    pages = set()
    for part in raw.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            pages.update(range(int(a), int(b) + 1))
        else:
            pages.add(int(part))
    return {p for p in pages if 1 <= p <= total}


# --- Main ---


def main():
    parser = argparse.ArgumentParser(description="Deep PDF parser for academic papers")
    parser.add_argument("--pdf", required=True, help="Path to the PDF file")
    parser.add_argument("--pages", help="Page range, e.g. '3-5' or '3,5,7'")
    parser.add_argument(
        "--sections", help="Section name filter (substring, case-insensitive)"
    )
    parser.add_argument("--output", default="json", choices=["json"])
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Error: File not found: {args.pdf}", file=sys.stderr)
        sys.exit(1)

    reader = PdfReader(str(pdf_path))
    total = len(reader.pages)

    metadata = extract_metadata(reader)

    pages_set = parse_page_range(args.pages, total)
    items = extract_text_items(reader, pages_set)
    items = order_two_columns(items)

    if args.sections:
        sections = detect_sections(items)
        matching = [s for s in sections if args.sections.lower() in s.title.lower()]
        if matching:
            filtered = []
            for s in matching:
                filtered.extend(items[s.start_line : s.end_line + 1])
            items = filtered

    full_text = " ".join(item.text for item in items)

    text_per_page = {}
    for item in items:
        key = str(item.page)
        text_per_page.setdefault(key, []).append(item.text)
    text_per_page = {k: " ".join(v) for k, v in text_per_page.items()}

    sections = detect_sections(items)
    sections_out = [
        {
            "title": s.title,
            "page": s.page,
            "start_line": s.start_line,
            "end_line": s.end_line,
        }
        for s in sections
    ]

    figures, tables = detect_figures_tables(full_text)
    equations = detect_equations(full_text)

    data = PaperData(
        metadata=metadata,
        full_text=full_text,
        text_per_page=text_per_page,
        sections=sections_out,
        figures=figures,
        tables=tables,
        equations=equations,
    )

    print(json.dumps(asdict(data), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

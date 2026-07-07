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
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import median

from _bootstrap import ensure_venv

ensure_venv(__file__)

import pdfplumber


# --- Section detection ---
SECTION_NUMBER_RE = re.compile(
    r"^\s*(?:\d{1,2}(?:\.\d{1,2})*[.)]?|[IVXLC]{1,4}[.)]|[A-Z][.)])\s+[A-Z]"
)
MATH_SYMBOLS = frozenset("−=+×≤≥→∇∈±·⊕⊗∑∏")
SECTION_VOCAB = frozenset(
    {
        "abstract",
        "introduction",
        "related work",
        "background",
        "method",
        "methods",
        "methodology",
        "approach",
        "architecture",
        "model",
        "experiment",
        "experiments",
        "evaluation",
        "results",
        "implementation",
        "discussion",
        "analysis",
        "ablation",
        "conclusion",
        "conclusions",
        "future work",
        "summary",
        "limitations",
        "references",
        "acknowledgment",
        "acknowledgments",
        "appendix",
    }
)

FIGURE_RE = re.compile(r"(?:Fig(?:ure)?\.?\s*(\d+))", re.IGNORECASE)
TABLE_RE = re.compile(r"(?:Table\.?\s*(\d+))", re.IGNORECASE)
EQUATION_RE = re.compile(r"(?:Eq(?:uation)?\s*\(?\s*(\d+)\s*\)?)", re.IGNORECASE)


@dataclass
class Word:
    text: str
    page: int
    x0: float
    x1: float
    top: float
    bottom: float
    size: float
    fontname: str


@dataclass
class Line:
    text: str
    page: int
    x0: float
    x1: float
    top: float
    bottom: float
    size: float
    fontname: str
    spanning: bool = False


@dataclass
class Paragraph:
    text: str
    page: int


@dataclass
class Section:
    title: str
    page: int
    start_line: int
    end_line: int
    text: str
    method: str


@dataclass
class PaperData:
    metadata: dict = field(default_factory=dict)
    full_text: str = ""
    text_per_page: dict = field(default_factory=dict)
    sections: list = field(default_factory=list)
    figures: list = field(default_factory=list)
    tables: list = field(default_factory=list)
    equations: list = field(default_factory=list)


# --- Word extraction ---


def extract_page_words(page, page_num):
    words = []
    width = page.width or 0.0
    margin = 0.07 * width
    raw = page.extract_words(
        x_tolerance=1.5,
        y_tolerance=2,
        keep_blank_chars=False,
        use_text_flow=False,
        extra_attrs=["size", "fontname", "upright"],
    )
    for w in raw:
        text = str(w.get("text", "")).strip()
        if not text:
            continue
        x0 = float(w["x0"])
        x1 = float(w["x1"])
        if not bool(w.get("upright", True)) and width:
            cx = (x0 + x1) / 2
            if cx < margin or cx > width - margin:
                continue
        words.append(
            Word(
                text=text,
                page=page_num,
                x0=x0,
                x1=x1,
                top=float(w["top"]),
                bottom=float(w["bottom"]),
                size=float(w.get("size", 0.0) or 0.0),
                fontname=str(w.get("fontname", "") or ""),
            )
        )
    return words


# --- Line grouping ---


def cluster_rows(words, y_tol=3.0):
    if not words:
        return []

    ordered = sorted(words, key=lambda w: (w.top, w.x0))
    rows = []
    current = [ordered[0]]
    anchor_top = ordered[0].top
    for w in ordered[1:]:
        if abs(w.top - anchor_top) <= y_tol and w.page == current[0].page:
            current.append(w)
        else:
            rows.append(current)
            current = [w]
            anchor_top = w.top
    rows.append(current)
    return rows


def line_from_words(words):
    group = sorted(words, key=lambda w: w.x0)
    sizes = [w.size for w in group if w.size > 0]
    fontnames = [w.fontname for w in group if w.fontname]
    return Line(
        text=" ".join(w.text for w in group),
        page=group[0].page,
        x0=min(w.x0 for w in group),
        x1=max(w.x1 for w in group),
        top=min(w.top for w in group),
        bottom=max(w.bottom for w in group),
        size=median(sizes) if sizes else 0.0,
        fontname=Counter(fontnames).most_common(1)[0][0] if fontnames else "",
    )


def group_lines(words, y_tol=3.0):
    return [line_from_words(row) for row in cluster_rows(words, y_tol)]


# --- Column detection & ordering ---


def detect_gutter(words, page_width):
    rows = cluster_rows(words)
    if len(rows) < 3 or page_width <= 0:
        return None

    min_gap = max(12.0, 0.03 * page_width)
    lo, hi = 0.3 * page_width, 0.7 * page_width
    centers = []
    for row in rows:
        row = sorted(row, key=lambda w: w.x0)
        best_gap = 0.0
        best_center = None
        for prev, cur in zip(row, row[1:]):
            gap = cur.x0 - prev.x1
            center = (prev.x1 + cur.x0) / 2
            if gap > best_gap and lo <= center <= hi and gap >= min_gap:
                best_gap = gap
                best_center = center
        if best_center is not None:
            centers.append(best_center)

    if len(centers) >= max(3, int(0.3 * len(rows))):
        return median(centers)
    return None


def order_lines(words, gutter, page_width):
    if not words:
        return []
    if gutter is None:
        return group_lines(words)

    min_gap = max(12.0, 0.03 * page_width)
    left = []
    right = []
    spanning = []
    for row in cluster_rows(words):
        row = sorted(row, key=lambda w: w.x0)
        left_ws = [w for w in row if (w.x0 + w.x1) / 2 < gutter]
        right_ws = [w for w in row if (w.x0 + w.x1) / 2 >= gutter]
        if left_ws and right_ws:
            crosses = any(w.x0 < gutter < w.x1 for w in row)
            gap = min(w.x0 for w in right_ws) - max(w.x1 for w in left_ws)
            if not crosses and gap >= min_gap:
                left.append(line_from_words(left_ws))
                right.append(line_from_words(right_ws))
            else:
                ln = line_from_words(row)
                ln.spanning = True
                spanning.append(ln)
        elif left_ws:
            left.append(line_from_words(left_ws))
        else:
            right.append(line_from_words(right_ws))

    seps = sorted(spanning, key=lambda ln: ln.top)
    result = []
    prev_top = float("-inf")
    for sep in seps + [None]:
        band_hi = sep.top if sep is not None else float("inf")
        band_left = sorted(
            (ln for ln in left if prev_top <= ln.top < band_hi),
            key=lambda ln: ln.top,
        )
        band_right = sorted(
            (ln for ln in right if prev_top <= ln.top < band_hi),
            key=lambda ln: ln.top,
        )
        result.extend(band_left)
        result.extend(band_right)
        if sep is not None:
            result.append(sep)
            prev_top = sep.top
    return result


def group_paragraphs(lines, gap_factor=1.5):
    if not lines:
        return []

    gaps = [
        lines[i].top - lines[i - 1].bottom
        for i in range(1, len(lines))
        if lines[i].top - lines[i - 1].bottom > 0
    ]
    median_gap = median(gaps) if gaps else 0.0
    threshold = median_gap * gap_factor if median_gap > 0 else float("inf")

    paragraphs = []
    current = [lines[0]]
    for i in range(1, len(lines)):
        prev, cur = lines[i - 1], lines[i]
        new_para = (
            cur.top < prev.top
            or (cur.top - prev.bottom) > threshold
            or cur.page != prev.page
        )
        if new_para:
            paragraphs.append(
                Paragraph(
                    text="\n".join(ln.text for ln in current), page=current[0].page
                )
            )
            current = [cur]
        else:
            current.append(cur)
    paragraphs.append(
        Paragraph(text="\n".join(ln.text for ln in current), page=current[0].page)
    )
    return paragraphs


# --- Section detection ---


def modal_size(lines):
    weights = Counter()
    for ln in lines:
        if ln.size > 0:
            weights[round(ln.size)] += len(ln.text)
    if not weights:
        return 0.0
    return float(weights.most_common(1)[0][0])


def fonts_uniform(lines):
    sizes = {round(ln.size) for ln in lines if ln.size > 0}
    bold = any(kw in ln.fontname.lower() for ln in lines for kw in ("bold", "black"))
    return len(sizes) <= 1 and not bold


def _strip_number(title):
    return re.sub(r"^\s*(?:\d+(?:\.\d+)*|[IVXLC]+|[A-Z])[.)]?\s+", "", title).strip()


def classify_header(line, body_size, uniform):
    text = line.text.strip()
    wc = len(text.split())

    # Conservative rejects: lines that cannot be genuine section headers.
    if len(text) <= 2 or text[0].islower():
        return False, "fallback"
    if any(c in MATH_SYMBOLS for c in text):
        return False, "fallback"
    alpha = sum(c.isalpha() for c in text)
    if alpha == 0 or alpha / len(text) < 0.5:
        return False, "fallback"

    score = 0
    typo = False
    num = False

    if not uniform:
        if body_size > 0 and line.size >= body_size * 1.15:
            score += 2
            typo = True
        if any(k in line.fontname.lower() for k in ("bold", "black", "semibold")):
            score += 2
            typo = True
    if SECTION_NUMBER_RE.match(text):
        score += 2
        num = True
    if wc <= 10:
        score += 1
    if text.isupper() and wc <= 10:
        score += 1

    normalized = _strip_number(text).lower()
    if normalized in SECTION_VOCAB or any(
        normalized.startswith(v) for v in SECTION_VOCAB
    ):
        score += 1

    is_header = score >= 3
    if uniform:
        method = "fallback"
    elif typo:
        method = "typographic"
    elif num:
        method = "numbered"
    else:
        method = "fallback"
    return is_header, method


def detect_sections(lines):
    if not lines:
        return []

    body = modal_size(lines)
    uniform = fonts_uniform(lines)

    headers = []
    for idx, ln in enumerate(lines):
        is_header, method = classify_header(ln, body, uniform)
        if is_header:
            headers.append((idx, method))

    sections = []
    for h, (start, method) in enumerate(headers):
        end = headers[h + 1][0] - 1 if h + 1 < len(headers) else len(lines) - 1
        slice_lines = lines[start : end + 1]
        text = "\n\n".join(p.text for p in group_paragraphs(slice_lines))
        sections.append(
            Section(
                title=lines[start].text.strip(),
                page=lines[start].page,
                start_line=start,
                end_line=end,
                text=text,
                method=method,
            )
        )
    return sections


# --- Figure / Table / Equation detection ---


def detect_references(text):
    def collect(regex):
        seen = {}
        for m in regex.finditer(text):
            num = int(m.group(1))
            if num not in seen:
                seen[num] = m.start()
        return [{"number": n, "position": seen[n]} for n in sorted(seen)]

    return collect(FIGURE_RE), collect(TABLE_RE), collect(EQUATION_RE)


# --- Metadata ---


def extract_year(meta, first_text):
    date = (
        meta.get("CreationDate")
        or meta.get("/CreationDate")
        or meta.get("ModDate")
        or meta.get("/ModDate")
        or ""
    )
    m = re.search(r"(?:D:)?((?:19|20)\d{2})", str(date))
    if m:
        return int(m.group(1))
    m = re.search(
        r"(?:©|\(c\)|copyright)\s*((?:19|20)\d{2})", first_text, re.IGNORECASE
    )
    if m:
        return int(m.group(1))
    return None


def extract_metadata(pdf, first_page_lines):
    meta = {}
    pdf_meta = pdf.metadata or {}
    for key in ("Title", "Author", "Creator", "Producer", "Subject"):
        val = pdf_meta.get(key) or pdf_meta.get("/" + key) or ""
        if val:
            meta[key.lower()] = str(val).strip()

    first_text = " ".join(ln.text for ln in first_page_lines)

    doi_m = re.search(r"(?:doi|DOI)[:\s]*(10\.\d{4,}/[^\s]+)", first_text)
    if doi_m:
        meta["doi"] = doi_m.group(1)

    year = extract_year(pdf_meta, first_text)
    if year is not None:
        meta["year"] = year

    if not meta.get("title") and first_page_lines:
        top_lines = [ln for ln in first_page_lines if ln.size > 0]
        if top_lines:
            max_size = max(ln.size for ln in top_lines)
            title_lines = [
                ln.text for ln in first_page_lines if abs(ln.size - max_size) < 0.5
            ]
            meta["extracted_title"] = " ".join(title_lines[:3])
        else:
            meta["extracted_title"] = first_page_lines[0].text

    return meta


# --- Page range parsing ---


def parse_page_range(raw, total):
    if not raw:
        return set(range(1, total + 1))
    pages = set()
    for part in raw.split(","):
        part = part.strip()
        try:
            if "-" in part:
                a, b = part.split("-", 1)
                lo, hi = int(a), int(b)
                if lo > hi:
                    raise ValueError
                pages.update(range(lo, hi + 1))
            else:
                pages.add(int(part))
        except ValueError:
            raise ValueError(f"invalid page range: {part!r}") from None
    return {p for p in pages if 1 <= p <= total}


# --- Main ---


def extract_document_lines(pdf, pages_set):
    all_lines = []
    word_count = 0
    total = len(pdf.pages)
    for page_num in sorted(pages_set):
        if page_num < 1 or page_num > total:
            continue
        page = pdf.pages[page_num - 1]
        words = extract_page_words(page, page_num)
        ordered = order_lines(words, detect_gutter(words, page.width), page.width)
        word_count += len(words)
        all_lines.extend(ordered)
    return all_lines, word_count


def collect_first_page_lines(pdf, pages_set, total):
    if 1 in pages_set or not pages_set:
        first_words = extract_page_words(pdf.pages[0], 1) if total else []
        return group_lines(first_words)
    return []


def filter_lines_by_section(all_lines, section_query):
    detected = detect_sections(all_lines)
    matching = [s for s in detected if section_query.lower() in s.title.lower()]
    if matching:
        filtered = []
        for s in matching:
            filtered.extend(all_lines[s.start_line : s.end_line + 1])
        return filtered
    return all_lines


def build_text_per_page(all_lines):
    text_per_page = {}
    page_lines = {}
    for ln in all_lines:
        page_lines.setdefault(ln.page, []).append(ln)
    for page_num, plines in page_lines.items():
        text_per_page[str(page_num)] = "\n\n".join(
            p.text for p in group_paragraphs(plines)
        )
    return text_per_page


def sections_to_dicts(sections):
    return [
        {
            "title": s.title,
            "page": s.page,
            "start_line": s.start_line,
            "end_line": s.end_line,
            "text": s.text,
            "method": s.method,
        }
        for s in sections
    ]


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

    try:
        pdf = pdfplumber.open(str(pdf_path))
    except Exception as e:
        print(f"Error: cannot open PDF: {e}", file=sys.stderr)
        sys.exit(1)

    with pdf:
        total = len(pdf.pages)

        try:
            pages_set = parse_page_range(args.pages, total)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        all_lines, word_count = extract_document_lines(pdf, pages_set)
        first_page_lines = collect_first_page_lines(pdf, pages_set, total)

        metadata = extract_metadata(pdf, first_page_lines)

        if word_count == 0:
            print(
                "Warning: no text layer found (scanned PDF?); consider OCR.",
                file=sys.stderr,
            )

        if args.sections:
            all_lines = filter_lines_by_section(all_lines, args.sections)

        full_text = "\n\n".join(p.text for p in group_paragraphs(all_lines))

        text_per_page = build_text_per_page(all_lines)

        sections_out = sections_to_dicts(detect_sections(all_lines))

        figures, tables, equations = detect_references(full_text)

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

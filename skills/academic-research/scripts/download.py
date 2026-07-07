#!/usr/bin/env python3
"""
Download academic papers with GB/T 7714-inspired structured filenames.

Resolves the target directory, builds a structured filename, downloads the
PDF, and idempotently maintains a papers/index.json index.

Usage:
  python download.py resolve --choice auto
  python download.py resolve --choice cwd
  python download.py resolve --choice temp
  python download.py fetch --dir ./papers --paper '<search-result-json>'
"""

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from paper import PaperResult

from _bootstrap import ensure_venv

ensure_venv(__file__)

import requests


def sanitize_segment(text):
    """Sanitize a string into a filename-safe, hyphen-joined segment."""
    if not text:
        return ""
    text = re.sub(r"\s+", "-", str(text))
    text = re.sub(r"[^A-Za-z0-9\-_.]", "", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def truncate_title(title, max_len=80):
    """Sanitize and truncate a title on word boundaries up to ``max_len``.

    Returns ``"Untitled"`` when the title is empty or has no usable words.
    """
    if not title:
        return "Untitled"
    words = [sanitize_segment(w) for w in str(title).split()]
    words = [w for w in words if w]
    if not words:
        return "Untitled"
    result = words[0]
    for word in words[1:]:
        if len(result) + 1 + len(word) > max_len:
            break
        result = f"{result}-{word}"
    return result


def build_filename(paper: PaperResult):
    """Build a GB/T 7714-inspired ``Author_Year_Title_Source.pdf`` filename."""
    author = sanitize_segment(paper.get("first_author_surname"))
    if not author or author.lower() == "unknown":
        author = "Unknown"
    else:
        author = author[0].upper() + author[1:]

    year = str(paper["year"]) if paper.get("year") else "nd"
    title = truncate_title(paper.get("title", ""))

    source_id = paper.get("source_id")
    doi = paper.get("doi")
    if source_id:
        source_seg = f"{paper.get('source')}-{sanitize_segment(str(source_id))}"
    elif doi:
        source_seg = sanitize_segment(str(doi).replace("/", "-"))
    else:
        source_seg = ""

    parts = [p for p in [author, year, title, source_seg] if p]
    return "_".join(parts) + ".pdf"


def dedup_key(paper: PaperResult, filename):
    """Return a stable dedup key: source id, else DOI, else filename."""
    if paper.get("source_id"):
        return f"{paper.get('source')}:{paper['source_id']}"
    if paper.get("doi"):
        return f"doi:{paper['doi']}"
    return f"file:{filename}"


def load_index(index_path):
    """Load the papers index JSON, returning an empty list if missing/invalid."""
    if not index_path.exists():
        return []
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []
    return data if isinstance(data, list) else []


def build_entry(paper: PaperResult, filename):
    """Build an index entry dict for a downloaded paper, with dedup key."""
    return {
        "filename": filename,
        "title": paper.get("title"),
        "authors": paper.get("authors") or [],
        "year": paper.get("year"),
        "source": paper.get("source"),
        "source_id": paper.get("source_id"),
        "doi": paper.get("doi"),
        "pdf_url": paper.get("pdf_url"),
        "downloaded_at": datetime.now().astimezone().isoformat(),
        "_key": dedup_key(paper, filename),
    }


def upsert_index(index, entry, key):
    """Insert or replace the entry with matching ``_key`` in ``index``."""
    for i, existing in enumerate(index):
        if existing.get("_key") == key:
            index[i] = entry
            return index
    index.append(entry)
    return index


def resolve_temp_dir():
    """Return a writable temp papers dir, falling back to the home directory."""
    base = Path(tempfile.gettempdir()) / "academic-research" / "papers"
    try:
        base.mkdir(parents=True, exist_ok=True)
        if os.access(base, os.W_OK):
            return base
    except OSError:
        pass
    return Path.home() / ".academic-research" / "papers"


def cmd_resolve(args):
    """Resolve the papers directory per ``--choice`` and print it.

    Returns an exit code: 0 on success, 3 when auto mode needs a user choice.
    """
    if args.choice == "auto":
        if (Path("papers") / "index.json").exists():
            print(str(Path("papers").resolve()))
            return 0
        print(
            "NEEDS_CHOICE: no papers/index.json in current directory",
            file=sys.stderr,
        )
        return 3
    if args.choice == "cwd":
        print(str(Path("papers").resolve()))
        return 0
    if args.choice == "temp":
        print(str(resolve_temp_dir()))
        return 0
    return 1


def download_pdf(url, dest):
    """Stream-download a PDF to ``dest``, removing a partial file on failure."""
    headers = {"User-Agent": "academic-research-skill/0.1"}
    try:
        with requests.get(url, stream=True, timeout=60, headers=headers) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        fh.write(chunk)
    except Exception:
        dest.unlink(missing_ok=True)
        raise


def cmd_fetch(args):
    """Download a paper (or reuse existing), update the index, print status.

    Returns an exit code: 0 on success, 1 when the paper has no ``pdf_url``.
    """
    paper: PaperResult = json.loads(args.paper)
    dest_dir = Path(args.dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = build_filename(paper)
    dest = dest_dir / filename
    index_path = dest_dir / "index.json"

    if dest.exists():
        status = "reused"
    else:
        pdf_url = paper.get("pdf_url")
        if not pdf_url:
            print(
                f"Error: no pdf_url for paper '{paper.get('title')}'",
                file=sys.stderr,
            )
            return 1
        download_pdf(pdf_url, dest)
        status = "downloaded"

    index = load_index(index_path)
    key = dedup_key(paper, filename)
    entry = build_entry(paper, filename)
    upsert_index(index, entry, key)
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(
        json.dumps(
            {"filename": filename, "path": str(dest), "status": status},
            ensure_ascii=False,
        )
    )
    return 0


def main():
    """CLI entry point: dispatch the ``resolve`` or ``fetch`` subcommand."""
    parser = argparse.ArgumentParser(
        description="Download academic papers with structured filenames"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve_p = subparsers.add_parser("resolve", help="Resolve the papers directory")
    resolve_p.add_argument(
        "--choice",
        choices=["auto", "cwd", "temp"],
        default="auto",
        help="Directory resolution strategy (default: auto)",
    )

    fetch_p = subparsers.add_parser("fetch", help="Download a paper and index it")
    fetch_p.add_argument("--paper", required=True, help="Search result JSON object")
    fetch_p.add_argument("--dir", required=True, help="Target papers directory")

    args = parser.parse_args()

    if args.command == "resolve":
        sys.exit(cmd_resolve(args))
    elif args.command == "fetch":
        sys.exit(cmd_fetch(args))


if __name__ == "__main__":
    main()

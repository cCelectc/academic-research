"""Shared schema for academic paper search results.

Defines the ``PaperResult`` structure produced by every search source in
``search.py`` and consumed by ``download.py``, plus helpers to build it in a
single place.
"""

import os
from typing import TypedDict

DEFAULT_USER_AGENT = (
    "academic-research-skill/0.1 (+https://github.com/cCelectc/academic-research)"
)


def user_agent() -> str:
    """Return the HTTP User-Agent, overridable via ``ACADEMIC_RESEARCH_UA``."""
    return os.environ.get("ACADEMIC_RESEARCH_UA", DEFAULT_USER_AGENT)


class PaperResult(TypedDict):
    """A unified academic paper record shared across search sources.

    All four search backends (arXiv, Semantic Scholar, DBLP, CORE) emit this
    exact key set so downstream tools can treat results uniformly.
    """

    source: str
    title: str
    authors: list[str]
    year: int | None
    abstract: str | None
    pdf_url: str | None
    doi: str | None
    source_id: str | None
    first_author_surname: str
    citation_count: int | None


def extract_surname(authors: list[str]) -> str:
    """Return the surname of the first author, or ``"unknown"``.

    Takes the last whitespace-separated token of ``authors[0]``. Falls back to
    ``"unknown"`` when the list is empty or the first name has no tokens.
    """
    if not authors:
        return "unknown"
    parts = authors[0].split()
    return parts[-1] if parts else "unknown"


def build_result(
    source: str,
    title: str,
    authors: list[str],
    year: int | None,
    abstract: str | None,
    pdf_url: str | None,
    doi: str | None,
    source_id: str | None,
    citation_count: int | None = None,
) -> PaperResult:
    """Assemble a ``PaperResult`` in one place.

    Computes ``first_author_surname`` from ``authors`` and fills the remaining
    fields from the given arguments, guaranteeing a consistent key set.
    """
    return {
        "source": source,
        "title": title,
        "authors": authors,
        "year": year,
        "abstract": abstract,
        "pdf_url": pdf_url,
        "doi": doi,
        "source_id": source_id,
        "first_author_surname": extract_surname(authors),
        "citation_count": citation_count,
    }

#!/usr/bin/env python3
"""
Multi-source academic paper search.
Queries arXiv, Semantic Scholar, DBLP, and CORE, outputs unified JSON.

Usage:
  python search.py --query "attention mechanism"
  python search.py --query "graph neural network" --sources arxiv,s2 --max-results 5
  python search.py --query "transformer" --output pretty
"""

import argparse
import json
import sys
import time

from paper import PaperResult, build_result, user_agent

from _bootstrap import ensure_venv

ensure_venv(__file__)

import xml.etree.ElementTree as ET
import requests


ARXIV_API = "http://export.arxiv.org/api/query"
S2_API = "https://api.semanticscholar.org/graph/v1/paper/search"
DBLP_API = "https://dblp.org/search/publ/api"
CORE_API = "https://api.core.ac.uk/v3/search/works"

USER_AGENT = user_agent()
HEADERS = {"User-Agent": USER_AGENT}

ARXIV_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def _extract_surname(authors):
    if not authors:
        return "unknown"
    parts = authors[0].split()
    return parts[-1] if parts else "unknown"


def _sanitize_text(text):
    if not text:
        return ""
    return text.strip().replace("\n", " ")


def search_arxiv(query, max_results) -> list[PaperResult]:
    """Search arXiv via its Atom API and return unified paper results."""
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
    }
    resp = requests.get(ARXIV_API, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    results = []
    for entry in root.findall("atom:entry", ARXIV_NS):
        title_el = entry.find("atom:title", ARXIV_NS)
        summary_el = entry.find("atom:summary", ARXIV_NS)
        id_el = entry.find("atom:id", ARXIV_NS)
        published_el = entry.find("atom:published", ARXIV_NS)

        title = _sanitize_text(title_el.text) if title_el is not None else ""
        summary = _sanitize_text(summary_el.text) if summary_el is not None else ""
        arxiv_id = (
            id_el.text.strip().split("/abs/")[-1]
            if id_el is not None and id_el.text
            else ""
        )
        published = (
            published_el.text.strip()
            if published_el is not None and published_el.text
            else ""
        )
        year = int(published[:4]) if published else None

        authors = []
        for a in entry.findall("atom:author", ARXIV_NS):
            name_el = a.find("atom:name", ARXIV_NS)
            if name_el is not None and name_el.text:
                authors.append(name_el.text.strip())

        doi = None
        for link in entry.findall("atom:link", ARXIV_NS):
            href = link.attrib.get("href", "")
            if "doi.org" in href:
                doi = href.split("doi.org/")[-1]

        results.append(
            build_result(
                source="arxiv",
                title=title,
                authors=authors,
                year=year,
                abstract=summary,
                pdf_url=f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else None,
                doi=doi,
                source_id=arxiv_id,
            )
        )
    return results


def search_semantic_scholar(query, max_results) -> list[PaperResult]:
    """Search the Semantic Scholar graph API and return unified results."""
    params = {
        "query": query,
        "limit": min(max_results, 100),
        "fields": "title,authors,year,abstract,externalIds,openAccessPdf,citationCount",
    }
    resp = requests.get(S2_API, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    results = []
    for paper in data.get("data", []):
        authors = [a["name"] for a in paper.get("authors", [])]
        oa = paper.get("openAccessPdf")
        pdf_url = oa.get("url") if oa else None
        doi = (paper.get("externalIds") or {}).get("DOI")
        results.append(
            build_result(
                source="semantic_scholar",
                title=paper.get("title", ""),
                authors=authors,
                year=paper.get("year"),
                abstract=(paper.get("abstract") or ""),
                pdf_url=pdf_url,
                doi=doi,
                source_id=paper.get("paperId"),
                citation_count=paper.get("citationCount"),
            )
        )
    return results


def search_dblp(query, max_results) -> list[PaperResult]:
    """Search the DBLP publication API and return unified results.

    Normalizes DBLP's single-vs-list author shapes into a list of names.
    """
    params = {
        "q": query,
        "format": "json",
        "h": str(max_results),
    }
    resp = requests.get(DBLP_API, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    results = []
    for hit in (data.get("result") or {}).get("hits", {}).get("hit", []):
        info = hit.get("info", {})
        title = info.get("title", "")
        year = info.get("year")
        if year:
            year = int(year)

        authors_list = info.get("authors", {})
        if isinstance(authors_list, dict):
            author_entries = authors_list.get("author", [])
            if isinstance(author_entries, dict):
                author_entries = [author_entries]
            authors = [a.get("text", "") for a in author_entries]
        else:
            authors = []

        results.append(
            build_result(
                source="dblp",
                title=title,
                authors=authors,
                year=year,
                abstract=None,
                pdf_url=None,
                doi=info.get("doi"),
                source_id=info.get("key"),
            )
        )
    return results


def search_core(query, max_results) -> list[PaperResult]:
    """Search the CORE works API and return unified results."""
    params = {
        "q": query,
        "limit": str(min(max_results, 100)),
    }
    resp = requests.get(CORE_API, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    results = []
    for work in data.get("results", []):
        authors = [a.get("name", "") for a in work.get("authors", [])]
        download_url = work.get("downloadUrl") or work.get("fullText")
        results.append(
            build_result(
                source="core",
                title=work.get("title", ""),
                authors=authors,
                year=work.get("yearPublished"),
                abstract=(work.get("abstract") or ""),
                pdf_url=download_url,
                doi=work.get("doi"),
                source_id=str(work.get("id", "")),
            )
        )
    return results


SOURCES = {
    "arxiv": search_arxiv,
    "s2": search_semantic_scholar,
    "dblp": search_dblp,
    "core": search_core,
}


def main():
    """CLI entry point: query the chosen sources and print results."""
    parser = argparse.ArgumentParser(description="Multi-source academic paper search")
    parser.add_argument("--query", required=True, help="Search keywords")
    parser.add_argument(
        "--sources",
        default="arxiv,s2,dblp,core",
        help="Comma-separated source names: arxiv,s2,dblp,core",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="Max results per source (default: 10)",
    )
    parser.add_argument(
        "--output",
        default="json",
        choices=["json", "pretty"],
        help="Output format (default: json)",
    )
    args = parser.parse_args()

    sources = [s.strip() for s in args.sources.split(",") if s.strip() in SOURCES]
    if not sources:
        print("Error: No valid sources specified.", file=sys.stderr)
        sys.exit(1)

    all_results = []
    for source_name in sources:
        print(f"Searching {source_name}...", file=sys.stderr)
        try:
            results = SOURCES[source_name](args.query, args.max_results)
            all_results.extend(results)
            print(f"  Found {len(results)} results", file=sys.stderr)
        except Exception as e:
            print(f"  Error searching {source_name}: {e}", file=sys.stderr)
        time.sleep(1)

    if args.output == "pretty":
        for i, r in enumerate(all_results, 1):
            print(f"\n{'=' * 60}")
            print(f"[{i}] [{r['source']}] {r['title']}")
            print(f"    Authors: {', '.join(r['authors']) if r['authors'] else 'N/A'}")
            print(f"    Year: {r['year'] if r['year'] else 'N/A'}")
            if r["abstract"]:
                abstract = r["abstract"][:300].replace("\n", " ")
                print(f"    Abstract: {abstract}...")
            if r["pdf_url"]:
                print(f"    PDF: {r['pdf_url']}")
            if r["doi"]:
                print(f"    DOI: {r['doi']}")
            if r["citation_count"] is not None:
                print(f"    Citations: {r['citation_count']}")
        print()
    else:
        json.dump(all_results, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()

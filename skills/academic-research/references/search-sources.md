# Search Source Reference

## arXiv

- **Base URL:** `http://export.arxiv.org/api/query`
- **Format:** XML (Atom feed)
- **Key parameters:** `search_query` (e.g. `all:attention mechanism`), `start`, `max_results`, `sortBy` (`relevance`, `lastUpdatedDate`, `submittedDate`)
- **Rate limit:** No documented hard limit. Recommended: 1 request per 3 seconds to avoid throttling
- **Coverage:** Physics, Mathematics, Computer Science, Quantitative Biology, Quantitative Finance, Statistics, Electrical Engineering, Economics
- **Notes:** Preprints only (no peer review guarantee). No citation data. Direct PDF links constructed from arXiv ID: `https://arxiv.org/pdf/{id}`. Response includes up to 3 author names per entry

## Semantic Scholar

- **Base URL:** `https://api.semanticscholar.org/graph/v1/paper/search`
- **Format:** JSON
- **Key parameters:** `query`, `limit` (max 100), `fields` (comma-separated: `title,authors,year,abstract,externalIds,openAccessPdf,citationCount`)
- **Rate limit:** 100 requests per 5 minutes without API key
- **Coverage:** 200M+ papers across all academic disciplines
- **Notes:** Provides citation counts, reference lists, and open access PDF links when available. Best general-purpose search engine in this skill. For higher rate limits, register a free API key

## DBLP

- **Base URL:** `https://dblp.org/search/publ/api`
- **Format:** JSON (use `?format=json`)
- **Key parameters:** `q` (keywords), `h` (hits per page, max 1000), `f` (first hit offset), `format=json`
- **Rate limit:** No documented hard limit. Recommended: 1 request per second
- **Coverage:** Computer Science only, organized by conference/journal venues and authors
- **Notes:** No abstracts or citation data. Best used for finding papers by specific venue or author. Excellent for CS bibliography and tracking a researcher's publication record

## CORE

- **Base URL:** `https://api.core.ac.uk/v3/search/works`
- **Format:** JSON
- **Key parameters:** `q` (keywords), `limit` (max 100)
- **Rate limit:** 30 requests per minute without API key
- **Coverage:** Aggregates open access repositories worldwide. Coverage less comprehensive than Semantic Scholar
- **Notes:** Provides direct PDF download links (`downloadUrl` or `fullText` field) for open access papers. Most useful when you need guaranteed full-text access

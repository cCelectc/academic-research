---
name: academic-research
description: >
  Search academic papers across arXiv, Semantic Scholar, DBLP, and CORE.
  Download PDFs and parse them deeply for sections, figures, equations with
  two-column layout handling. Provide interactive reading assistance with
  bilingual translation and plain-language formula explanation.
  Engage in research brainstorming with adaptive mentor/peer reviewer modes.
  Use when the user mentions academic research, literature review, paper
  search, paper download, paper reading, arXiv, or wants to discuss research
  ideas and get reviewer-style feedback — even if they don't use the exact
  words "academic" or "research."
license: MIT
metadata:
  version: "0.1.0"
---

# Academic Research

A complete academic research workflow: search for papers, download them, parse and
summarize PDFs, interactively read, and brainstorm ideas.

This skill bundles two self-contained Python scripts in `scripts/` and reference
docs in `references/`. The scripts handle their own Python environment so you
can call them directly.

Think of three modes, switching naturally based on what the user asks:

- **Search** — find papers by topic or keywords
- **Read** — parse a PDF and interact with its content
- **Discuss** — brainstorm research ideas as a mentor or peer reviewer

## Search & Download

When the user wants to find papers, run the search script:

```bash
python scripts/search.py --query "agent memory implementation" --sources arxiv,s2,dblp,core
```

The script prints a JSON array to stdout. Each result has: `source`, `title`,
`authors`, `year`, `abstract`, `pdf_url`, `doi`, `source_id`,
`first_author_surname`, `citation_count`.

Present results as a numbered list showing the source tag, title, authors, year,
and the first 2-3 sentences of the abstract. Include the PDF URL when available.
Ask which papers to download.

To narrow the search:

```bash
python scripts/search.py --query "attention mechanism" --sources arxiv,s2 --max-results 20
python scripts/search.py --query "graph neural network" --output pretty
```

For API details and rate limits, see `references/search-sources.md`.

### Downloading a paper

Downloads are handled by `scripts/download.py`, which resolves the storage
directory, builds a structured filename, downloads the PDF, and maintains a
`papers/index.json` index.

**Step 1 — resolve the storage directory.** Run:

```bash
python scripts/download.py resolve --choice auto
```

- Exit code `0`: the printed path is the directory to use (an existing
  `papers/index.json` was found in the current directory — keep appending there).
- Exit code `3` (`NEEDS_CHOICE`): no index exists yet. Ask the user where to
  store papers, then re-run with their choice:
  - Temporary workspace (cross-platform, cross-agent): `--choice temp`
  - Current directory: `--choice cwd`

Remember the resolved path and reuse it for all downloads in this session.

**Step 2 — fetch the paper.** Pass the chosen search result JSON object (from
`search.py`) to the `fetch` subcommand:

```bash
python scripts/download.py fetch --dir "<resolved-dir>" --paper '<result-json>'
```

The script prints `{"filename": ..., "path": ..., "status": "downloaded"|"reused"}`.
It builds the filename, downloads the PDF (reusing an existing file instead of
overwriting), and idempotently updates `index.json`.

**Filename format** (GB/T 7714-inspired structure):

```
{FirstAuthorSurname}_{Year}_{Title}_{Source}-{SourceID}.pdf
```

Example: `Vaswani_2017_Attention-Is-All-You-Need_arxiv-1706.03762.pdf`

- Surname capitalized; title truncated at ~80 chars on word boundaries, words
  joined by `-`; missing author → `Unknown`, missing year → `nd`.
- Sanitization: spaces → `-`; only `A-Za-z0-9-_.` kept; `:` `/` `?` `,` etc.
  removed; consecutive `-` collapsed. DOI does not go in the filename.
- If `source_id` is missing, the sanitized DOI is used as the trailing segment;
  if both are missing, the segment is omitted.

**index.json** is a JSON array; each entry has: `filename`, `title`, `authors`,
`year`, `source`, `source_id`, `doi`, `pdf_url`, `downloaded_at` (ISO 8601).
Deduplication key is `source`+`source_id`, falling back to `doi`, then
`filename` — re-downloading the same paper updates its entry instead of adding
a duplicate.

## Parsing a Paper

Once a PDF is downloaded, parse it:

```bash
python scripts/parse_pdf.py --pdf "papers/Author_2024_Paper_Title.pdf"
```

The output is a JSON object with these top-level keys:

| Key | Contents |
|-----|----------|
| `metadata` | title, author, doi, year (extracted from PDF properties and first-page text) |
| `full_text` | complete paper text; paragraphs separated by `\n\n`, wrapped lines by `\n` |
| `text_per_page` | dict mapping page number (string) to page text (same `\n\n`/`\n` formatting) |
| `sections` | array of `{title, page, start_line, end_line, text, method}` for each detected section (`method` is `typographic`, `numbered`, or `fallback`; `text` uses the same `\n\n`/`\n` formatting) |
| `figures` | array of `{number, position}` for detected Figure references (deduplicated by number) |
| `tables` | array of `{number, position}` for detected Table references (deduplicated by number) |
| `equations` | array of `{number, position}` for detected Equation references (deduplicated by number) |

For specific pages or sections:

```bash
python scripts/parse_pdf.py --pdf "papers/x.pdf" --pages "3-5"
python scripts/parse_pdf.py --pdf "papers/x.pdf" --sections "Methodology"
```

Section names match by substring (case-insensitive). Use the `sections` array from a
full parse to discover exact section titles.

## Summarizing a Paper

After parsing, generate a structured summary. If your platform supports subagents
(parallel task execution), dispatch one subagent per major section to summarize in
parallel. Otherwise process sections sequentially.

Cover these four dimensions:

1. **Core Contribution** — 1-2 sentences: what problem does this paper solve and how?
2. **Method / Architecture** — Key technical approach: model structure, algorithm
   design, or system architecture. Be concrete about the mechanism.
3. **Key Results** — Main findings with numbers (accuracy, speedup, etc.) and which
   baselines they surpass.
4. **Notable Limitations** — Limitations the authors acknowledge or boundaries the
   reader should be aware of.

## Interactive Reading

When the user asks about a specific passage, figure out what they mean and locate it
in the parsed JSON:

| User says | How to locate |
|-----------|--------------|
| "page 3, paragraph 2" or "第3页第2段" | Read `text_per_page["3"]`, split with `.split("\n\n")`, return the paragraph at the given index (1-based) |
| Pastes or quotes a sentence | Search `full_text` for the quoted substring, return the surrounding 3-5 sentences |
| "Methodology, paragraph 3" or "Methodology 第3段" | Find the section whose title contains the name (substring, case-insensitive), split its `text` with `.split("\n\n")`, return the Nth paragraph |

**Match your response language to the user's language.** If they write in Chinese,
respond in Chinese. If they write in English, respond in English. If mixed, follow
the dominant language.

For each located passage, provide three things:

1. **Summary** — 2-3 sentences capturing the key point, in the user's language
2. **Bilingual comparison** — The original text as written in the paper, followed
   by a translation into the user's language, in clearly separated blocks. If the
   paper is already in the user's language, skip the translation
3. **Plain-language explanation** — If the passage has formulas, algorithms, or
   technical jargon, explain them in simple terms. Describe what each variable
   represents and why the formula is shaped that way. Use everyday analogies
   where helpful

## Research Brainstorming

When the user expresses evaluative, hypothetical, or brainstorming intent —
e.g. "do you think this approach is feasible", "what if we replaced Transformers
with Mamba", "I've been thinking about...", or the equivalents in other languages
— switch into discussion mode. Read `references/peer-review-guide.md` for the
full behavior spec.

This skill auto-detects whether the user is a novice or experienced researcher:

- **Mentor mode** (novice): Narrow their direction, provide background knowledge,
  recommend foundational papers, critique gently, pace one point at a time
- **Peer mode** (experienced): Assess feasibility, difficulty, and novelty with
  specific citations. Always suggest 1-3 search queries to explore related work

Stay in concise tool mode for search, download, and parse tasks. Switch to discussion
mode only when the user invites it.

## Scripts Self-Bootstrap

All three scripts — `scripts/search.py`, `scripts/parse_pdf.py`, and
`scripts/download.py` — handle their own environment automatically. The first
time you run any of them:

1. Checks if `uv` is available in PATH
2. With uv: `uv venv .venv && uv pip install --python .venv/bin/python requests pdfplumber`
3. Without uv: `python -m venv .venv && .venv/bin/pip install requests pdfplumber`
4. Re-executes itself with the venv Python

Subsequent runs reuse the `.venv/` with zero overhead. No setup command needed.

## File Structure

```
academic-research/
├── SKILL.md                       (this file)
├── scripts/
│   ├── pyproject.toml             (dependency declarations)
│   ├── search.py                  (multi-source search CLI)
│   ├── parse_pdf.py               (deep PDF parser CLI)
│   └── download.py                (download, structured naming, index maintenance)
└── references/
    ├── search-sources.md          (API reference per source)
    └── peer-review-guide.md       (mentor/peer interaction modes)
```

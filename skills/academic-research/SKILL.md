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

After the user picks a paper by number, download it:

```bash
mkdir -p papers
curl -L -o "papers/<Firstauthor>_<Year>_<TitleWords>.pdf" "<pdf_url>"
```

Build the filename from the search result: `first_author_surname` + `_` + `year` +
`_` + first three words of the title. Sanitize: uppercase first letter of each word,
replace spaces with underscores, remove characters that aren't alphanumeric,
underscores, hyphens, or dots.

If a paper has no `pdf_url` but has a DOI, try `curl -L "https://doi.org/<doi>"`
as a fallback. Warn the user it may lead to a paywall.

## Parsing a Paper

Once a PDF is downloaded, parse it:

```bash
python scripts/parse_pdf.py --pdf "papers/Author_2024_Paper_Title.pdf"
```

The output is a JSON object with these top-level keys:

| Key | Contents |
|-----|----------|
| `metadata` | title, author, doi, year (extracted from PDF properties and first-page text) |
| `full_text` | complete paper text as a single string |
| `text_per_page` | dict mapping page number (string) to page text |
| `sections` | array of `{title, page, start_line, end_line}` for each detected section |
| `figures` | array of `{number, position}` for detected Figure references |
| `tables` | array of `{number, position}` for detected Table references |
| `equations` | array of `{number, position}` for detected Equation references |

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
| "page 3, paragraph 2" or "第3页第2段" | Read `text_per_page["3"]`, split by double-newline or sentence boundaries, return the paragraph at the given index (1-based) |
| Pastes or quotes a sentence | Search `full_text` for the quoted substring, return the surrounding 3-5 sentences |
| "Methodology, paragraph 3" or "Methodology 第3段" | Find the section whose title contains the name (substring, case-insensitive), split its text by paragraphs, return the Nth |

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

Both `scripts/search.py` and `scripts/parse_pdf.py` handle their own environment
automatically. The first time you run either:

1. Checks if `uv` is available in PATH
2. With uv: `uv venv .venv && uv pip install requests pypdf`
3. Without uv: `python -m venv .venv && .venv/bin/pip install requests pypdf`
4. Re-executes itself with the venv Python

Subsequent runs reuse the `.venv/` with zero overhead. No setup command needed.

## File Structure

```
academic-research/
├── SKILL.md                       (this file)
├── scripts/
│   ├── pyproject.toml             (dependency declarations)
│   ├── search.py                  (multi-source search CLI)
│   └── parse_pdf.py               (deep PDF parser CLI)
└── references/
    ├── search-sources.md          (API reference per source)
    └── peer-review-guide.md       (mentor/peer interaction modes)
```

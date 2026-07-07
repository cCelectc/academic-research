# academic-research

An [Agent Skills](https://agentskills.io) for terminal-based AI agents
(Claude Code, OpenCode, Cursor, Codex, etc.) that provides a complete academic
research workflow.

## What it does

- **Search** papers across arXiv, Semantic Scholar, DBLP, and CORE — all free, no API key needed
- **Download** PDFs to `papers/` with clean filenames
- **Parse** PDFs deeply — metadata, sections, figures, equations, two-column layout
- **Read** interactively — summarize, translate, explain formulas in plain language
- **Discuss** research ideas with adaptive mentor/peer reviewer modes

## Install

```bash
npx skills add cCelectc/academic-research
```

Or copy `skills/academic-research/` into your agent's skills directory.

## Quick Start

Once the skill is loaded by your agent, just talk to it:

```
> Find recent papers about agent memory mechanisms
> Download paper #3
> Parse it
> Explain the architecture in section 3
> What if we applied this to multimodal agents?
```

## Structure

```
skills/academic-research/
├── SKILL.md                       # Main instructions
├── scripts/
│   ├── pyproject.toml             # Dependencies (requests, pypdf)
│   ├── search.py                  # Multi-source search CLI
│   └── parse_pdf.py               # Deep PDF parser CLI
└── references/
    ├── search-sources.md          # API details per source
    └── peer-review-guide.md       # Mentor/peer interaction modes
```

## Requirements

- Python 3.9+
- `uv` recommended (auto-falls back to `venv + pip`)
- `curl` or `wget` for downloads
- Internet access for API calls

Scripts bootstrap their own virtual environment on first run — no manual setup.

## Data Sources

| Source | Coverage | Has Abstracts | Has PDF Links | Has Citations |
|--------|----------|:---:|:---:|:---:|
| arXiv | CS, Physics, Math, Bio | Yes | Yes (direct) | No |
| Semantic Scholar | 200M+ papers, all disciplines | Yes | OA only | Yes |
| DBLP | CS bibliography | No | No | No |
| CORE | OA repositories worldwide | Partial | Yes (OA) | No |

## License

MIT

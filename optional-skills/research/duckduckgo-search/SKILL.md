---
name: duckduckgo-search
description: Free web search via DuckDuckGo — text, news, images, and videos with no API key. Use as a fallback when no paid search provider is configured, or when the agent needs quick, anonymous web lookups during research, recall enrichment, or answering a chat question that needs fresh facts.
version: 1.0.0
author: TaskChad OS
license: MIT
platforms: [linux, macos, windows]
metadata:
  taskchad:
    category: research
    tags: [search, web, duckduckgo, free, fallback]
    related_skills: [arxiv-digest]
    mutates: false
---

# DuckDuckGo Search

Free, keyless web search. No account, no API key. Good default when a paid
search provider (Serper, Tavily, etc.) is not configured in `.env`.

## Two runtimes, two install paths

The terminal and any `execute_code` sandbox are **separate environments**. A
successful shell install does not guarantee the package imports inside the code
runtime — verify in the runtime you actually use.

**CLI (preferred):**

```bash
uv run python optional-skills/research/duckduckgo-search/scripts/search.py \
  "homie framework memory pipeline" --type text --max 5
```

**Python:** import `DDGS` only after confirming it exists.

```python
from ddgs import DDGS  # pip/uv install ddgs first
with DDGS() as ddgs:
    results = list(ddgs.text("query here", max_results=5))  # keyword arg, not positional
```

## Usage notes

- `max_results` must be a **keyword** argument.
- Results are snippets + URLs, not full pages. Pair with a fetch/extract step
  when you need the body text.
- DuckDuckGo throttles bursts — space out repeated calls.
- Search types: `text` (general), `news` (recent), `images`, `videos`.

## Feeding results into memory

When a search answers a durable question, write the finding (with its source
URL) into the vault via the memory pipeline rather than leaving it in chat — see
`.claude/sections/03_*` for the recall/reflect flow.

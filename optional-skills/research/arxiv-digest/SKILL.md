---
name: arxiv-digest
description: Search arXiv for papers on a topic, then summarize the most relevant results into a vault note. Use when the user asks to keep up with research, find papers on a subject, or digest a specific arXiv paper into durable memory. Pairs with web search for citations and follow-up.
version: 1.0.0
author: TaskChad OS
license: MIT
platforms: [linux, macos, windows]
metadata:
  taskchad:
    category: research
    tags: [arxiv, papers, research, summarize, memory]
    related_skills: [duckduckgo-search]
    mutates: false
---

# arXiv Digest

Search arXiv and turn results into a concise, source-linked vault note.

## Query

The arXiv API is keyless. Hit the Atom endpoint directly:

```bash
curl -s "http://export.arxiv.org/api/query?search_query=all:%22memory%20consolidation%22+AND+cat:cs.AI&sortBy=submittedDate&sortOrder=descending&max_results=10"
```

`search_query` operators: `all:`, `ti:` (title), `abs:` (abstract), `au:`
(author), `cat:` (category, e.g. `cs.AI`, `cs.CL`). Combine with `AND`/`OR`.
URL-encode quoted phrases.

## Digest workflow

1. Parse the Atom feed: per entry pull `title`, `summary`, `author`, `published`,
   and the `id` (the arXiv URL).
2. Rank by relevance to the user's topic; keep the top 3–5.
3. For each kept paper write 2–3 sentences: the claim, the method, why it matters
   to this user's goals.
4. Write the digest to the vault as a dated note with every source URL inline,
   so later recall can cite it. Follow the memory-write path in
   `.claude/sections/03_*`.

## Output shape

```markdown
# arXiv digest — <topic> — <date>

## <paper title>
<arXiv URL>
<2–3 sentence summary>. Relevance: <one line>.
```

Keep it skimmable. Do not paste full abstracts — summarize.

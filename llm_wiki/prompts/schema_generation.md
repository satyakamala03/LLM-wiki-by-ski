You are setting up a personal knowledge base wiki focused on: **{domain}**.

Write a complete SCHEMA.md file that will serve as the rulebook for this wiki. An LLM agent will read this file when creating and updating wiki pages, so be precise and practical.

The wiki root contains these directories (already created on disk):

- `raw/` — original source documents; never modified by the agent
- `summaries/` — one page per ingested source article
- `entities/` — specific things: ingredients, products, people, brands, dishes (e.g. aquafaba, JUST Egg, King Arthur Baking)
- `topics/` — broader overview and synthesis pages (e.g. comparing egg substitutes for cookies)

Your SCHEMA.md must include these sections:

## 1. Purpose

Brief description of what this wiki covers and who it is for.

## 2. Directory conventions

Explain what belongs in each directory (`raw/`, `summaries/`, `entities/`, `topics/`) with 2–3 eggless-baking examples each.

## 3. File naming

Rules for markdown filenames (use kebab-case, e.g. `aquafaba.md`, `flax-egg.md`, `serious-eats-egg-substitute-test.md`).

## 4. YAML frontmatter

Every wiki page (except files in `raw/`) must start with YAML frontmatter between `---` delimiters.

**Required fields** (non-negotiable):

- `title` — human-readable page title
- `type` — one of: `entity`, `concept`, `summary`, `overview`
- `created` — date created (YYYY-MM-DD)
- `updated` — date last updated (YYYY-MM-DD)
- `tags` — list of keywords, e.g. `[vegan, foaming, baking]`
- `sources` — list of source filenames from `raw/` this page draws from; use `[]` if none yet

Explain when to use each `type` value with eggless-baking examples.

Provide one complete example frontmatter block for each type (`entity`, `concept`, `summary`, `overview`).

## 5. Cross-references

Use **{link_style_description}** for links between wiki pages.
Explain how to link from a summary to an entity, and from a topic overview to related concepts.
Include 2–3 link examples using real eggless-baking page names.

## 6. Agent guidelines

Short bullet list: be consistent with naming, flag contradictions between sources, never edit files in `raw/`, update `updated` when revising a page.

## 7. Refinement note

End the document with a short note that this schema is a starting draft and should be refined manually over time as the wiki grows.

Write only the SCHEMA.md content. Do not wrap it in code fences. Use markdown headings and bullet lists. Be specific to eggless baking — mention aquafaba, flax egg, emulsification, binding vs leavening where relevant.
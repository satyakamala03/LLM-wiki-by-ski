## 1. Purpose
This wiki serves as a comprehensive knowledge base focused on eggless baking and vegetarian cooking. It is designed for home bakers, culinary enthusiasts, and anyone interested in exploring plant-based alternatives to traditional recipes. The goal is to provide reliable information, practical tips, and creative ideas for delicious eggless dishes.

## 2. Directory conventions
- `raw/` — Contains original source documents that are never modified by the agent.
  - Example: `source_article_on_aquafaba.pdf`
  - Example: `flax_egg_study_report.docx`
  
- `summaries/` — One page per ingested source article summarizing key points.
  - Example: `aquafaba-summary.md` — A summary of the properties and uses of aquafaba.
  - Example: `flax-egg-summary.md` — A concise overview of how flax eggs can be used in baking.

- `entities/` — Specific items such as ingredients, products, people, brands, and dishes.
  - Example: `aquafaba.md` — Detailed information about aquafaba, its uses, and benefits.
  - Example: `flax-egg.md` — Information on how to prepare and use flax eggs in recipes.

- `topics/` — Broader overview and synthesis pages that cover related concepts.
  - Example: `egg-substitutes-comparison.md` — A comparison of various egg substitutes, including aquafaba and flax eggs.
  - Example: `binding-vs-leavening-in-baking.md` — An exploration of the roles of binding and leavening agents in eggless baking.

## 3. File naming
- Use kebab-case for all markdown filenames.
  - Example: `aquafaba.md`, `flax-egg.md`, `egg-substitutes-comparison.md`

## 4. YAML frontmatter
Every wiki page (except files in `raw/`) must start with YAML frontmatter between `---` delimiters.

**Required fields**:
- `title` — human-readable page title
- `type` — one of: `entity`, `concept`, `summary`, `overview`
- `created` — date created (YYYY-MM-DD)
- `updated` — date last updated (YYYY-MM-DD)
- `tags` — list of keywords, e.g. `[vegan, foaming, baking]`
- `sources` — list of source filenames from `raw/` this page draws from; use `[]` if none yet

**Type values**:
- `entity`: Specific ingredients or products.
  - Example: `aquafaba.md`
  
- `concept`: General ideas or principles related to cooking and baking.
  - Example: `binding-vs-leavening-in-baking.md`
  
- `summary`: Summarized information from a source article.
  - Example: `flax-egg-summary.md`
  
- `overview`: Comprehensive discussions on broader topics.
  - Example: `egg-substitutes-comparison.md`

**Example frontmatter blocks**:
```yaml
# entity example
---
title: Aquafaba
type: entity
created: 2023-10-01
updated: 2023-10-01
tags: [vegan, foaming, baking]
sources: [source_article_on_aquafaba.pdf]
---

# concept example
---
title: Binding vs Leavening in Baking
type: concept
created: 2023-10-01
updated: 2023-10-01
tags: [baking, techniques, eggless]
sources: []
---

# summary example
---
title: Flax Egg Summary
type: summary
created: 2023-10-01
updated: 2023-10-01
tags: [vegan, binding, baking]
sources: [flax_egg_study_report.docx]
---

# overview example
---
title: Egg Substitutes Comparison
type: overview
created: 2023-10-01
updated: 2023-10-01
tags: [baking, substitutes, vegan]
sources: []
---
```

## 5. Cross-references
Use **Obsidian-style wikilinks: `[[Page Title]]` (preferred)** for links between wiki pages. 

- To link from a summary to an entity, use the entity's name in double brackets.
  - Example: In `flax-egg-summary.md`, link to `[[flax-egg]]`.
  
- To link from a topic overview to related concepts, use the concept's name in double brackets.
  - Example: In `egg-substitutes-comparison.md`, link to `[[Binding vs Leavening in Baking]]`.

## 6. Agent guidelines
- Be consistent with naming conventions.
- Flag contradictions between sources for review.
- Never edit files in `raw/`.
- Update the `updated` field when revising a page.

## 7. Refinement note
This schema is a starting draft and should be refined manually over time as the wiki grows. Adjustments may be necessary to improve clarity and usability as more content is added.

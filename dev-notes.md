# Dev Notes — LLM Wiki

Living design and development documentation for this project.  
**Source of truth for requirements:** `coding-challenge-122-database-driven-llm-wiki.md`  
**Implementation guide:** `build-plan.md` (helper only — do not treat as overriding the challenge spec)  
**Last updated:** 2026-06-26 — Phase 8 complete (Steps 0–8); Streamlit browse + chat + save answer  
**Architecture diagrams:** [architecture.md](architecture.md) — update each phase

---

## Project status

| Phase | Challenge step | Status | Notes |
|-------|----------------|--------|-------|
| Environment setup | Step 0 | Done | Oracle Docker, corpus, Nomic embeddings |
| Wiki scaffolding | Step 1 | Done | `create-wiki`, frontmatter, SCHEMA.md |
| Source ingestion | Step 2 | Done | Batch LangGraph pipeline |
| Index & log (deep) | Step 3 | Done | `index_log/`, hybrid one-liners, timestamped log |
| Vector + Oracle search | Step 4 | Done | `wiki_pages`, vector + FTS indexes, RRF hybrid search, `embed-wiki` |
| Query system | Step 5 | Done | LangGraph query, `query` + `chat` CLI, save-to-wiki |
| Multi-wiki / Oracle projects | Step 6 | Done | `wiki_projects` table, `list-projects`, `sync-project`, isolation by `project_name` |
| Lint | Step 7 | Done | LangGraph lint, structural + LLM checks, interactive fixes, `wikis/lint-test/` |
| UI | Step 8 | Done | Streamlit `app.py` — browse, chat, save answer; ingest via `cli.py ingest` |

**Active wiki:** `wikis/eggless-baking/` (eggless baking & vegetarian cooking)  
**Lint fixtures:** `wikis/lint-test/` (controlled Phase 7.5 test pages)  
**Test corpus:** `corpus/raw/` (15 scraped articles; staging before ingest)

---

## Repository layout

```
LLM-wiki-by-ski/
  app.py                      # Streamlit UI entry (Phase 8)
  cli.py                      # Dev CLI entry point
  dev-notes.md                # This file
  build-plan.md               # Personal implementation plan
  coding-challenge-122-...md  # Challenge spec (authoritative)
  .streamlit/config.toml      # Streamlit server config (file watcher)

  llm_wiki/                   # Application code
    config/.env               # Secrets (never commit)
    env.py                    # TF/transformers + Streamlit compat env
    wiki/                     # Phase 1 — scaffolding
    ingestion/                # Phase 2 — LangGraph pipeline
    index_log/                # Phase 3 — index.md, log.md, readers
    db/                       # Phase 4 — Oracle connection, schema
    embeddings/               # Phase 4 — Nomic embed + sync
    search/                   # Phase 4 — vector, FTS, hybrid (RRF)
    query/                    # Phase 5 — LangGraph query + save answer
    projects/                 # Phase 6 — Oracle wiki_projects registry
    lint/                     # Phase 7 — LangGraph lint + fixes
    ui/                       # Phase 8 — Streamlit panels
    prompts/                  # LLM prompt templates

  wikis/                      # Wiki data (one folder per project)
    lint-test/                # Phase 7.5 lint verification fixtures
  corpus/                     # Pre-ingest article staging
    raw/
    sources.yaml              # Scrape URL list
  scripts/
    scrape_corpus.py          # Batch article downloader
    verify_lint.py            # Phase 7.5 lint verification
```

**Rule:** Code lives under `llm_wiki/`. Wiki content lives under `wikis/<name>/`. Never hardcode a wiki name in core logic — always pass `wiki_root` or `wiki_name`.

---

## Design decisions

### Wiki-agnostic / multi-domain

- Every operation is scoped to a wiki path or name.
- Each wiki has its own `SCHEMA.md`, pages, and `raw/` sources.
- Future wikis (e.g. `research-papers`) reuse the same pipeline; only domain + schema differ.
- Oracle `project_name` scoping on all embed/search/query operations (Phase 4–5); metadata registry in Phase 6.

### Directory layout (Option A — locked)

Challenge directories: `raw/`, `summaries/`, `entities/`, `topics/` — no separate `concepts/` folder.

| Folder | `type` in frontmatter | Contents |
|--------|----------------------|----------|
| `raw/` | _(none)_ | Original sources; **never modified by agent** |
| `summaries/` | `summary` | One page per ingested source |
| `entities/` | `entity` | Ingredients, products, brands, people, dishes |
| `topics/` | `concept` **or** `overview` | Ideas/techniques vs broad synthesis pages |

**Type definitions**

- **entity** — specific, nameable thing (Aquafaba, JUST Egg, King Arthur)
- **concept** — idea/mechanism (Emulsification, Leavening, Binding)
- **summary** — distilled single source
- **overview** — synthesis across sources (Egg Substitutes Comparison)

### YAML frontmatter (required on all wiki pages except `raw/`)

```yaml
---
title: Page Title
type: entity | concept | summary | overview
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [tag1, tag2]
sources: [raw-filename.md]
index_summary: One-line catalogue sentence for index (optional; set at write time)
---
```

- Implemented in `llm_wiki/wiki/frontmatter.py`
- `new_frontmatter()` defaults `created` / `updated` to today when omitted
- `write_page()` validates before writing

### Cross-references

- Default: Obsidian wikilinks `[[Page Title]]`
- Resolution: match `title` in frontmatter, then kebab-case filename fallback
- Implemented in `llm_wiki/wiki/wiki_manager.py` (`resolve_wikilink`, used by `inspect-wiki`)

### SCHEMA.md

- Per-wiki rulebook; loaded into ingestion state as `schema_text` for every LLM prompt
- Generated via `generate_schema()` (OpenAI) or written manually
- Overwriting `SCHEMA.md` never touches other wiki files

### Raw source rule

```
corpus/raw/article.md  ──copy──►  wikis/<wiki>/raw/article.md  (read-only forever)
```

- `prepare_source()` copies once; reuses existing raw file if present
- Agent writes only to `summaries/`, `entities/`, `topics/`, `index.md`, `log.md`

### Interactive mode

| Feature | Status | Notes |
|---------|--------|-------|
| Batch ingest | **Implemented** | Default for Phase 2 |
| Interactive takeaways (Step 2) | Deferred | Optional `--interactive` flag; ingest stays CLI |
| Interactive contradiction fixes | **Implemented** | Phase 7 lint — approve/reject per issue (`cli.py lint`) |
| Auto-note contradictions on pages | **Implemented** | `## Contradictions` section appended |

---

## CLI commands

Run from project root with `python3`:

```bash
# Wiki management (Phase 1)
python3 cli.py create-wiki <name>
python3 cli.py create-wiki <name> --generate-schema --domain "..." [--link-style wikilink|markdown]
python3 cli.py list-wikis
python3 cli.py inspect-wiki <name>

# Ingestion (Phase 2)
python3 cli.py ingest <wiki-name> <path-to-source.md>

# Index & log (Phase 3)
python3 cli.py show-index <wiki-name>
python3 cli.py show-log <wiki-name> [--tail N]
python3 cli.py rebuild-index <wiki-name>

# Oracle + search (Phase 4)
python3 cli.py db-ping
python3 cli.py db-init [--rebuild-indexes]
python3 cli.py db-status <wiki-name>
python3 cli.py embed-wiki <wiki-name> [--force] [--prune]
python3 cli.py search <wiki-name> "<query>" [--mode hybrid|vector|fts] [--top-k 10]

# Query (Phase 5)
python3 cli.py query <wiki-name> "<question>" [--top-k 8] [--save] [--no-save-prompt]
python3 cli.py chat <wiki-name> [--top-k 8]

# Multi-wiki projects (Phase 6)
python3 cli.py list-projects
python3 cli.py sync-project <wiki-name>

# Lint (Phase 7)
python3 cli.py lint <wiki-name> [--checks structural|llm|all]
python3 cli.py lint <wiki-name> --report-only
python3 cli.py lint <wiki-name> --auto-fix
python3 scripts/verify_lint.py

# Corpus scraping (Phase 0)
python3 scripts/scrape_corpus.py --limit 15

# Web UI (Phase 8)
streamlit run app.py
```

Global option: `--wikis-dir wikis` (default)

### Streamlit UI (Phase 8)

**Run:** `streamlit run app.py` (from repo root; loads `llm_wiki/config/.env`)

| Area | Behavior |
|------|----------|
| Sidebar | Wiki selector, page tree (Sources / Entities / Concepts / Overviews), chat `top_k` slider, clear history |
| Browse | Markdown viewer; `[[wikilinks]]` navigate via `?page=` |
| Chat | `run_query` with follow-up `messages`; spinner; linkified citations |
| Save | Per-answer expander → `save_answer_as_page` → `topics/` + index + embed |

**Ingest (no UI):** `python3 cli.py ingest <wiki> <file.md>`

**Env notes:** `USE_TF=0`, `TRANSFORMERS_NO_TF=1` in `.env` (see `.env.example`); `.streamlit/config.toml` sets `fileWatcherType = none` for PyTorch.

**Module:** `llm_wiki/ui/` — `main`, `sidebar`, `browse`, `viewer`, `chat`, `wikilinks`, `errors`, `state`

---

## LangGraph ingestion pipeline

**Entry:** `llm_wiki/ingestion/graph.py` → `run_ingestion(wiki_name, source_path)`

### Mental model

- **State** — shared dict (`IngestionState`) passed between steps
- **Node** — one Python function, one job; returns partial state updates
- **Edge** — execution order
- **`invoke()`** — run the full pipeline once

### Node order

```
read_source
  → extract_info          (LLM → JSON)
  → write_summary_page    (LLM → summaries/)
  → update_entity_pages   (LLM → entities/)
  → update_concept_pages  (LLM → topics/, type: concept)
  → update_topic_pages    (LLM → topics/, type: overview)
  → detect_contradictions (LLM → append ## Contradictions)
  → flag_gaps             (LLM → stub entity pages)
  → sync_embeddings       (Oracle upsert for pages_written)
  → update_index          (rebuild index.md via index_log)
  → append_log            (ingest or ingest-failed entry)
```

### Index one-liners (Phase 3)

- **Hybrid:** LLM generates `index_summary` in frontmatter at page write time (Ollama in dev).
- **`rebuild-index`** reads stored `index_summary`; **heuristic fallback** (first body paragraph) if missing — no LLM on rebuild.
- Index section for summaries is **`## Sources`** (files still live in `summaries/`).
- Index entries include path, `created`, and source count.

**Config** (`llm_wiki/config/.env`):

```bash
INDEX_ONELINER_PROVIDER=ollama   # or heuristic
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
```

**Module:** `llm_wiki/index_log/` — `index_builder`, `log_writer`, `oneliner`, `readers`

### Oracle embeddings (Phase 4)

- **Table:** `wiki_pages` — `embed_text`, `search_text`, `embedding VECTOR(768)`, `content_hash`, scoped by `project_name` (= wiki folder name)
- **Embed input:** `title + index_summary` (heuristic fallback if FM field missing)
- **Search input:** `title + index_summary + body` (Oracle Text)
- **Incremental:** `content_hash` on `embed_text`; skip unchanged rows
- **Hybrid merge:** RRF (`k=60`) over vector + FTS top-20 → top-10
- **Ingestion:** `sync_embeddings` node after `flag_gaps` (non-fatal warnings)
- **DDL:** `python3 cli.py db-init` or `scripts/init_oracle_schema.sql`
- **Env:** set `USE_TF=0` before embedding (Keras 3 / transformers conflict)
- **Oracle dev note:** `db-init` sets `SYSTEM` default tablespace to `USERS` (vector indexes require ASSM)

**Verified (eggless-baking):** 12 disk pages = 12 Oracle rows; FTS `"aquafaba"` and vector `"plant binding"` return sensible hits.

**Module:** `llm_wiki/db/`, `llm_wiki/embeddings/`, `llm_wiki/search/`

### Query system (Phase 5)

**Graph:** `load_context → hybrid_search → read_pages → synthesize_answer → append_query_log`

- Bootstrap: index + recent log + SCHEMA excerpt via `load_wiki_context`
- Retrieval: hybrid search top-8, read full pages (18k char budget)
- Synthesis: `query_synthesize.md` — wikilink citations, coverage `full|partial|none`
- Follow-ups: `chat` CLI accumulates `messages`; search query prepends prior topic
- Save answer: prompt or `--save` → new `topics/` overview page + index + embed + log

**Module:** `llm_wiki/query/`

### Multi-wiki project registry (Phase 6)

- **Table:** `wiki_projects` — `name`, `wiki_path`, `created_at`, `last_ingestion`, `last_query`, `page_count`, `source_count`, `embedding_count`, `updated_at`
- **Scoping:** `project_name` (= wiki folder name) on all `wiki_pages` embed/search/query operations
- **Sync hooks:** `create-wiki`, successful `ingest`, `embed-wiki`, `query`/`chat`, save answer → `sync_project_metadata` (non-fatal warnings)
- **CLI:** `list-projects` merges disk wikis + Oracle rows; `sync-project` backfills metadata
- **Isolation verified:** `search vr-research-papers "aquafaba"` → no results; `search eggless-baking "aquafaba"` → hits

**Module:** `llm_wiki/projects/`

### Lint system (Phase 7)

**Graph:** `load_context → structural_checks → llm_checks → prioritize_findings`

| Pass | Module | Severity | Checks |
|------|--------|----------|--------|
| Structural | `structural.py` | Warning | orphan, broken/missing wikilink, invalid frontmatter |
| LLM | `llm_checks.py` | Critical / Suggestion | contradiction, stale claim, data gaps + research prompts |

**Fix loop (CLI, after report):** interactive by default; `--report-only` / `--no-fix-prompt` skip fixes; `--auto-fix` applies all `auto_fixable` issues.

| `fix_kind` | Action |
|------------|--------|
| `create_stub` | LLM stub page for missing `[[target]]` |
| `add_backlink` | Append orphan to `index.md` |
| `append_contradiction` | `## Contradictions` on involved pages |
| `revise_claim` | `## Revision note` on stale page |

**Post-fix:** `rebuild_index` → `sync_page_paths` → `log lint` → `try_sync_project`

**Prompts:** `lint_contradiction.md`, `lint_stale_claim.md`, `lint_gaps.md`

**Verification:** `wikis/lint-test/` + `python3 scripts/verify_lint.py`

**Module:** `llm_wiki/lint/`, `llm_wiki/wiki/contradictions.py`

### Streamlit UI (Phase 8)

See **CLI reference → Streamlit UI** above. Challenge Step 8 checklist:

- [x] Launch interface and access it
- [x] Ask questions — markdown + wikilink citations
- [x] Click citation → opens page in Browse
- [x] Follow-up questions retain context
- [x] Browse tree reflects pages on disk
- [x] Save answer as wiki page (sidebar updates)
- [x] Ingest via CLI without launching UI
- [x] Loading spinner during query

**Optional (not built):** `llm-wiki` thin CLI wrapper; lint UI; in-app ingest.

### IngestionState key fields

| Field | Purpose |
|-------|---------|
| `wiki_root` | Absolute path to wiki |
| `source_path` | Path under `raw/` |
| `source_text` | Full article text |
| `schema_text` | Contents of `SCHEMA.md` |
| `extraction` | JSON: entities, concepts, overviews, claims |
| `pages_written` | Relative paths touched |
| `contradictions` | Records of flagged conflicts |
| `gaps_flagged` | Stub pages created |
| `embed_embedded` / `embed_skipped` | Oracle sync counts (Phase 4) |
| `embed_warnings` | Non-fatal embed errors |
| `errors` | Fatal issues (stops meaningful output) |

### Prompt files (`llm_wiki/prompts/`)

| File | Node |
|------|------|
| `ingest_extract.md` | `extract_info` |
| `ingest_summary.md` | `write_summary_page` |
| `ingest_entity.md` | `update_entity_pages` |
| `ingest_concept.md` | `update_concept_pages` |
| `ingest_topic.md` | `update_topic_pages` |
| `ingest_contradiction.md` | `detect_contradictions` |
| `ingest_gap_stub.md` | `flag_gaps` |
| `lint_contradiction.md` | lint `llm_checks` |
| `lint_stale_claim.md` | lint `llm_checks` |
| `lint_gaps.md` | lint `llm_checks` |
| `schema_generation.md` | `generate_schema()` (Phase 1) |

**LLM default:** `gpt-4o-mini` via LangChain OpenAI integration.  
**Config:** `llm_wiki/config/.env` → `OPENAI_API_KEY`

---

## Environment & infrastructure

| Component | Purpose | Status |
|-----------|---------|--------|
| OpenAI API | Ingestion + schema LLM | Configured |
| Ollama (local) | Index one-liners at write time | Optional (`INDEX_ONELINER_PROVIDER=ollama`) |
| LangChain + LangGraph | LLM + workflow | Installed |
| Oracle Database 26ai (Docker) | Vectors + full-text (Phase 4+) | Set up in Phase 0 |
| Nomic embeddings (`nomic-ai/nomic-embed-text-v2-moe`) | 768-dim vectors (Phase 4) | Tested in Phase 0 |
| `python-frontmatter` | Parse/write wiki pages | In use |
| `click` | CLI | In use |
| `langchain-ollama` | Ollama one-liners (Phase 3) | In use |
| `oracledb` | Oracle connectivity (Phase 4) | In use |
| `sentence-transformers` | Nomic embeddings (Phase 4) | In use |
| `trafilatura` | Corpus scraping | In use |

---

## Extending to new domains (e.g. research papers)

1. `python3 cli.py create-wiki research-papers --generate-schema --domain "ML research papers"`
2. Tune `SCHEMA.md` (entity types, citation conventions)
3. Optionally add PDF→text preprocessor in `ingestion/source.py`
4. `python3 cli.py ingest research-papers ./papers/some-paper.md`
5. Phase 6: `sync-project research-papers` registers wiki in Oracle (automatic on create/ingest)

Same graph, same CLI shape, different wiki folder + schema.

---

## Known implementation notes

- **CLI flag naming:** `--generate-schema` maps to `should_generate_schema` in code to avoid shadowing the `generate_schema()` function.
- **Oracle password:** avoid `@` in passwords when using `sqlplus` on the command line (zsh/shell parsing).
- **Docker disk:** Oracle image is large; Docker Desktop virtual disk can fill independently of Mac free space.
- **Index/log:** Phase 3 module (`index_log/`) owns index rebuild and log format. Stale entries drop automatically when pages are deleted.
- **Log events:** `ingest`, `ingest-failed`, `index-rebuild`, `embed-sync`, `query`, `lint` (plus reserved: `schema-change`).
- **Log format:** `## [YYYY-MM-DD HH:MM:SS] event-type | description` (date-only entries from before Phase 3 still parse).
- **Re-ingest:** Merging updates existing pages by title match; `sources` list is unioned; `updated` is bumped.

---

## Ingestion testing checklist (Step 2)

- [x] Ingest one article → summary, entity, topic pages on disk
- [x] Raw source copied, not modified on re-read
- [x] Frontmatter valid on generated pages
- [ ] Second contradictory source → `## Contradictions` on relevant page
- [ ] Mentioned entity without page → stub created
- [ ] Summary does not hallucinate facts absent from source (manual review)

**Suggested test sequence**

1. `king-arthur-guide-aquafaba.md`
2. `serious-eats-egg-substitutes-tested.md` (contradictions)
3. `minimalist-baker-flax-egg.md` (gaps / new entities)

---

## Lint testing checklist (Step 7)

- [x] Deliberate contradiction → lint reports both pages (`lint-test` test-alpha / test-beta)
- [x] Orphan page flagged
- [x] Broken wikilink reported
- [x] Data gap / research suggestions (LLM)
- [x] Accept fix → stub, index entry, or Contradictions section applied
- [x] Reject fix → fixture pages unchanged (`verify_lint.py`)

```bash
python3 scripts/verify_lint.py
```

---

## What's next

| Item | Focus |
|------|-------|
| Optional | `llm-wiki` CLI wrapper around `cli.py ingest` |
| Optional | Lint panel in Streamlit |
| Going further | Challenge “Going Further” ideas (graph viz, scheduled lint, etc.) |

---

*Last updated: 2026-06-26 — Phase 8 Streamlit UI complete. Synced with [architecture.md](architecture.md).*

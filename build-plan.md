## Your Build Plan: Database-Driven LLM Wiki (Cooking Domain)

### How to read this plan

Each phase maps to one of the challenge's steps. Within each phase, I've broken down the substeps into concrete tasks. When something is unfamiliar to you — vectors, LangGraph, etc. — I'll flag it with a **📚 80/20** note: the minimum mental model you need to move forward, nothing more.

---

## Phase 0 — Environment Setup

**Goal:** Get everything installed and talking to each other before writing any real code.

**Substeps:**

1. Create your project repo and a `.env` file. Rule #1: nothing sensitive in source code, ever. You'll store your OpenAI key and DB password here.
2. **Pull and run Oracle Database 26ai in Docker.** This is a free Oracle DB image that supports both vector search and full-text search — that's why the challenge uses it instead of plain Postgres.
  📚 *80/20:* Docker is just a way to run a database without installing it on your machine. Two commands and it's running. You connect to it like any other database via port 1521.
3. **Set up your embedding model.** Install `sentence-transformers` and load `nomic-ai/nomic-embed-text-v2-moe`. Run a quick test: pass in a string, get back a list of 768 numbers. That's it.
  📚 *80/20:* An embedding is just a way to turn text into a list of numbers so that similar texts produce similar numbers. You don't need to understand the math — just know that "pasta carbonara recipe" and "how to make carbonara" will produce vectors that are close to each other, and that's what powers semantic search later.
4. **Verify your OpenAI API key** works with a simple `chat.completions.create` call in Python.
5. **Install LangChain and LangGraph.** `pip install langchain langgraph langchain-openai`.
  📚 *80/20:* LangChain is a toolkit that wraps LLM API calls with useful patterns. LangGraph is for building *workflows* where you want steps to happen in sequence with state carried through — think of it like a flowchart you can actually run. You'll use it in Phase 2 onwards.
6. **Gather your cooking corpus.** 50–100 short articles (Serious Eats, Kenji's writing, food science pieces, technique explainers). Save as `.md` or `.txt` files in a `raw/` folder. Tip: Obsidian Web Clipper (a browser extension) converts web articles to markdown in one click.

**Checkpoint:** DB is running, embedding model returns a 768-dim vector, OpenAI responds, `.env` loads cleanly.

---

## Phase 1 — Wiki Scaffolding

**Goal:** Build the file system layer — the directory structure and conventions your wiki lives in.

**Substeps:**

1. Write a `wiki_manager.py` module with a `create_wiki(name, path)` function. It should create this folder structure:
  ```
   wikis/cooking/
     raw/          ← source documents go here, never modified
     summaries/    ← one page per source
     entities/     ← pages for ingredients, chefs, techniques
     topics/       ← broader overview pages
     SCHEMA.md     ← the "rules" for this wiki
     index.md      ← catalogue of all pages (built later)
     log.md        ← append-only history (built later)
  ```
2. Generate `SCHEMA.md` with an LLM call. Give it a prompt like: *"You are setting up a cooking knowledge base wiki. Write a SCHEMA.md that defines directory conventions, YAML frontmatter fields, and wikilink formatting rules."* You'll refine this over time.
3. Define your YAML frontmatter template. Every wiki page should start with:
  ```yaml
   ---
   title: Maillard Reaction
   type: concept
   created: 2026-06-10
   updated: 2026-06-10
   tags: [chemistry, browning, technique]
   sources: []
   ---
  ```
4. Build a minimal CLI (`cli.py`) with three commands: `create-wiki`, `list-wikis`, `inspect-wiki`. Use Python's `argparse` or the `click` library (easier).

**Checkpoint:** Run `python cli.py create-wiki cooking`. See the folder structure on disk. Manually drop a couple of test `.md` files with frontmatter and verify they parse with `python-frontmatter` library.

---

## Phase 2 — Source Ingestion Pipeline

**Goal:** The core of the system. Drop an article in, the agent updates the wiki across multiple pages.

**Substeps:**

1. **Learn the LangGraph mental model** (📚 80/20): A LangGraph workflow is a directed graph where each node is a Python function that receives a `state` dict and returns an updated `state` dict. You define the nodes, connect them with edges, and call `.invoke()`. That's 90% of what you need to know.
2. Design your ingestion graph with these nodes (each is one Python function):
  - `read_source` → reads the file
  - `extract_info` → LLM call: pull out entities, concepts, key claims
  - `write_summary_page` → LLM call: write a summary `.md` file
  - `update_entity_pages` → for each entity found, create/update its page
  - `update_concept_pages` → same for concepts
  - `detect_contradictions` → compare new claims against existing pages
  - `flag_gaps` → stub out pages for entities not yet covered
3. Write your prompts carefully. The quality of your wiki depends on these. Start simple, iterate. Example for extraction:
  > *"Read the following cooking article. Extract: (1) named entities (chefs, restaurants, dishes, ingredients), (2) key concepts and techniques, (3) factual claims. Return as JSON."*
4. Handle the raw source correctly — copy it into `raw/`, never touch it again.

**Checkpoint:** Ingest one short Serious Eats article. Verify that summary, entity, and concept pages appear on disk. Check that a second contradictory article causes the agent to flag the conflict on the relevant page.

---

## Phase 3 — Index and Log

**Goal:** Two special files that let the agent (and you) navigate the wiki as it grows.

**Substeps:**

1. After every ingestion, add a final node to your LangGraph graph: `update_index`. It reads all pages' frontmatter and rewrites `index.md` as a categorized catalogue with links and one-liners.
2. Add another final node: `append_log`. Every operation appends one line:
  ```
   ## [2026-06-10] ingest | Serious Eats - The Food Lab: Pasta
  ```
3. Make the agent *read the index first* on every query (you'll build the query system in Phase 5, but wire this habit in now).

**Checkpoint:** Ingest three sources. `index.md` lists all new pages. `grep "^\#\# \[" log.md` returns a clean chronological list. Delete a page manually, re-ingest something, verify `index.md` removes the stale entry.

---

## Phase 4 — Vector + Full-Text Search

**Goal:** Store embeddings in Oracle DB so the agent can find pages by meaning, not just by browsing the index.

**Substeps:**

1. 📚 *80/20 on vector search:* You're storing a 768-number fingerprint of each page. When you search, you convert your query to the same format and find the pages whose fingerprints are most similar (cosine similarity). Oracle has a native `VECTOR` column type and does this in SQL.
2. Design your Oracle table:
  ```sql
   CREATE TABLE wiki_pages (
     id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
     project_name VARCHAR2(100),
     page_path VARCHAR2(500),
     title VARCHAR2(200),
     page_type VARCHAR2(50),
     tags VARCHAR2(500),
     snippet CLOB,
     embedding VECTOR(768),
     updated_at TIMESTAMP
   );
  ```
3. Create two indexes: a **vector index** on the `embedding` column (for semantic search) and an **Oracle Text full-text index** on `snippet` (for exact-term search).
4. Write an `embed_and_store(page_path)` function. After any ingestion node writes or updates a page, call this. Only re-embed pages that changed.
5. Write a `hybrid_search(query, project)` function that runs both searches and merges results.

**Checkpoint:** Embed all pages in your test wiki. Query Oracle directly. Search "browning meat" and verify the Maillard Reaction page comes back even though those words aren't in the title.

---

## Phase 5 — Query System

**Goal:** Ask the wiki a question in plain English, get a cited answer.

**Substeps:**

1. Design the query LangGraph graph:
  - `read_index` → load `index.md` to get an overview
  - `hybrid_search` → find relevant pages via Oracle
  - `read_pages` → fetch full content of top N results
  - `synthesize_answer` → LLM call: answer using only what's in the pages, cite them
  - `offer_to_save` → ask if the answer should become a wiki page
2. Write your synthesis prompt carefully:
  > *"You are answering a question about cooking using only the following wiki pages. Cite each page by title when you use it. If the wiki doesn't cover the question, say so — do not speculate."*
3. Add conversation state to carry follow-up context (LangGraph handles this via its `state` object).
4. Support saving a good answer back to the wiki as a new page — this is what makes explorations compound.

**Checkpoint:** Ask "what makes a good sear on a steak?" — should cite multiple pages. Ask a follow-up "what temperature?" — should understand context. Ask about something not in your wiki — should admit the gap.

---

## Phase 6 — Multi-Wiki Project Management

**Goal:** Support multiple isolated knowledge bases (cooking, reading notes, etc.)

**Substeps:**

1. Add a `wiki_projects` table to Oracle:
  ```sql
   CREATE TABLE wiki_projects (
     id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
     name VARCHAR2(100) UNIQUE,
     created_at TIMESTAMP,
     last_ingestion TIMESTAMP,
     page_count NUMBER,
     source_count NUMBER
   );
  ```
2. Scope all queries and embeddings by `project_name` — searches against the cooking wiki never touch the reading-notes wiki.
3. Add `--project` flag to your CLI.

**Checkpoint:** Create two wikis with different topics. Queries against one return zero results from the other. Restart your system — everything persists.

---

## Phase 7 — Lint System

**Goal:** The agent health-checks the wiki and finds problems you didn't notice.

**Substeps:**

1. Build a `lint` LangGraph workflow with checks for:
  - Contradictions between pages
  - Orphan pages (nothing links to them)
  - Broken wikilinks
  - Concepts mentioned but without their own page
  - Stale claims newer sources override
2. Output a prioritized report: **Critical → Warnings → Suggestions**
3. Make it interactive by default — agent proposes a fix, you approve before anything changes.

**Checkpoint:** Deliberately create a contradiction and an orphan page. Run lint. Both are caught and reported with the specific pages involved.

---

## Phase 8 — User Interface

**Goal:** A proper interface instead of a dev CLI.

**Substeps:**

1. Choose your interface: the challenge allows either a web UI or a richer CLI chat. For a solo project, a **Streamlit** web UI is the fastest path in Python — it's basically Python code that becomes a UI.
2. Build a chat panel that renders markdown and makes citation links clickable.
3. Add a sidebar showing the wiki page tree (entities / concepts / summaries / topics).
4. Add a loading spinner for when the agent is processing.
5. Add a CLI shortcut for ingestion: `python cli.py ingest cooking ./new-article.md` — no need to launch the full UI just to add a source.

---

## Unfamiliar components, ranked by learning curve


| Component          | Your familiarity | Effort to 80/20           |
| ------------------ | ---------------- | ------------------------- |
| Oracle DB + Docker | Low              | ~2 hrs — mostly setup     |
| Vector embeddings  | Low              | ~30 min conceptually      |
| LangGraph          | Low              | ~1 hr — one tutorial pass |
| LangChain          | Low              | ~30 min — mostly wrappers |
| OpenAI API         | Low-ish          | ~15 min                   |
| Streamlit (UI)     | Unknown          | ~1 hr                     |


---

## Suggested sequence and time estimate

Phases 0–1 in your first session (setup + scaffolding). Phases 2–3 are the meatiest — budget several sessions there. Phases 4–5 are where it becomes genuinely useful. 6–8 are refinement.

---

That's the full plan. 
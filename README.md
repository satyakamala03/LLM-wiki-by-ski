# LLM Wiki

A database-driven personal knowledge base with an LLM agent that ingests sources, maintains a markdown wiki, answers questions with citations, lint-checks consistency, and provides a Streamlit web UI.

Built for [Coding Challenge #122 — Database-Driven LLM Wiki](coding-challenge-122-database-driven-llm-wiki.md).

## Features (Phases 0–8)

- Wiki scaffolding with YAML frontmatter and `SCHEMA.md`
- LangGraph source ingestion → summaries, entities, topics
- Hybrid index one-liners + timestamped activity log
- Oracle vector + full-text hybrid search (Nomic 768-dim)
- Query/chat with cited answers and save-to-wiki
- Multi-wiki project registry (`wiki_projects`)
- Lint: structural + LLM checks with interactive fixes
- **Streamlit UI:** browse page tree, chat with follow-ups, save answers

## Quick start

```bash
pip install -r requirements.txt
cp llm_wiki/config/.env.example llm_wiki/config/.env
# Edit .env with your OPENAI_API_KEY and Oracle credentials

python3 cli.py db-ping
python3 cli.py list-projects
python3 cli.py query eggless-baking "How does aquafaba work as an egg substitute?"
python3 cli.py lint eggless-baking --checks structural --report-only

# Web UI (browse + chat)
streamlit run app.py
```

Add sources without the UI:

```bash
python3 cli.py ingest eggless-baking corpus/raw/king-arthur-guide-aquafaba.md
```

See [dev-notes.md](dev-notes.md) for full CLI reference and [architecture.md](architecture.md) for diagrams.

## Layout

```
app.py              # Streamlit UI
cli.py              # Dev CLI
llm_wiki/           # Application code (ui/, query/, ingestion/, …)
wikis/              # Wiki projects (eggless-baking, lint-test, …)
.streamlit/         # Streamlit config
corpus/raw/         # Staging articles before ingest
scripts/            # scrape_corpus.py, verify_lint.py, Oracle DDL
```

## Docs

- [dev-notes.md](dev-notes.md) — design decisions, CLI, phase status
- [architecture.md](architecture.md) — Mermaid architecture diagrams
- [build-plan.md](build-plan.md) — personal implementation notes

## License

Personal learning project; challenge spec © John Crickett / Coding Challenges.

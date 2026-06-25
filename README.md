# LLM Wiki

A database-driven personal knowledge base with an LLM agent that ingests sources, maintains a markdown wiki, answers questions with citations, and lint-checks consistency.

Built for [Coding Challenge #122 — Database-Driven LLM Wiki](coding-challenge-122-database-driven-llm-wiki.md).

## Features (Phases 0–7)

- Wiki scaffolding with YAML frontmatter and `SCHEMA.md`
- LangGraph source ingestion → summaries, entities, topics
- Hybrid index one-liners + timestamped activity log
- Oracle vector + full-text hybrid search (Nomic 768-dim)
- Query/chat with cited answers and save-to-wiki
- Multi-wiki project registry (`wiki_projects`)
- Lint: structural + LLM checks with interactive fixes

## Quick start

```bash
pip install -r requirements.txt
cp llm_wiki/config/.env.example llm_wiki/config/.env
# Edit .env with your OPENAI_API_KEY and Oracle credentials

python3 cli.py db-ping
python3 cli.py list-projects
python3 cli.py query eggless-baking "How does aquafaba work as an egg substitute?"
python3 cli.py lint eggless-baking --checks structural --report-only
```

See [dev-notes.md](dev-notes.md) for full CLI reference and [architecture.md](architecture.md) for diagrams.

## Layout

```
cli.py              # Dev CLI
llm_wiki/           # Application code
wikis/              # Wiki projects (eggless-baking, lint-test, …)
corpus/raw/         # Staging articles before ingest
scripts/            # scrape_corpus.py, verify_lint.py, Oracle DDL
```

## Docs

- [dev-notes.md](dev-notes.md) — design decisions, CLI, phase status
- [architecture.md](architecture.md) — Mermaid architecture diagrams
- [build-plan.md](build-plan.md) — personal implementation notes

## License

Personal learning project; challenge spec © John Crickett / Coding Challenges.

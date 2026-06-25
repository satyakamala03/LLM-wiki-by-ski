"""Save a query answer back into the wiki."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from llm_wiki.embeddings.sync import sync_page_paths
from llm_wiki.index_log import append_log_entry, enrich_meta_with_index_summary, rebuild_index
from llm_wiki.index_log.log_writer import LOG_EVENT_QUERY
from llm_wiki.projects import try_sync_project
from llm_wiki.wiki.frontmatter import new_frontmatter, write_page
from llm_wiki.wiki.wiki_manager import title_to_slug


def save_answer_as_page(
    wiki_root: Path | str,
    project_name: str,
    *,
    title: str,
    body: str,
    page_type: str = "overview",
    tags: list[str] | None = None,
) -> Path:
    """Write answer as a new wiki page, rebuild index, embed, and log."""
    wiki_root = Path(wiki_root).resolve()
    slug = title_to_slug(title)
    if not slug:
        raise ValueError("Could not derive filename from title")

    page_path = wiki_root / "topics" / f"{slug}.md"
    if page_path.is_file():
        slug = f"{slug}-answer"
        page_path = wiki_root / "topics" / f"{slug}.md"

    meta = new_frontmatter(
        title,
        page_type,
        tags=list(tags or ["query-answer"]),
        sources=[],
    )
    meta = enrich_meta_with_index_summary(meta, body)
    write_page(page_path, meta, body)

    rel_path = page_path.relative_to(wiki_root).as_posix()
    rebuild_index(wiki_root)
    sync_page_paths(project_name, wiki_root, [rel_path])
    append_log_entry(wiki_root, LOG_EVENT_QUERY, f"saved answer as [[{title}]]")
    try_sync_project(project_name, wiki_root, last_query=datetime.now())

    return page_path

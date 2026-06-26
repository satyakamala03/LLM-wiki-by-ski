#!/usr/bin/env python3
"""Development CLI for LLM Wiki."""

from __future__ import annotations

import llm_wiki.env  # noqa: F401 — before embeddings / search imports

from datetime import datetime
from pathlib import Path

import click

from llm_wiki.db import ensure_schema, ping_oracle
from llm_wiki.embeddings.sync import count_project_pages, sync_wiki
from llm_wiki.index_log import (
    LOG_EVENT_EMBED_SYNC,
    LOG_EVENT_INDEX_REBUILD,
    append_log_entry,
    get_index_stats,
    read_index,
    read_log,
    read_log_tail,
    rebuild_index,
)
from llm_wiki.ingestion.graph import run_ingestion
from llm_wiki.ingestion.source import resolve_wiki_root
from llm_wiki.lint import (
    apply_fix,
    finalize_wiki_changes,
    format_lint_report,
    preview_fix,
    run_lint,
    should_skip_issue,
)
from llm_wiki.projects import list_all_projects, sync_project_metadata, try_sync_project
from llm_wiki.query import run_query, save_answer_as_page
from llm_wiki.search import hybrid_search
from llm_wiki.wiki.schema_generator import SchemaGenerationError, generate_schema
from llm_wiki.wiki.wiki_manager import (
    WikiExistsError,
    create_wiki,
    inspect_wiki,
    iter_content_pages,
    list_wikis,
    validate_wiki_name,
)

DEFAULT_WIKIS_DIR = Path("wikis")


def _sync_project_quiet(
    wiki_name: str,
    wiki_root: Path,
    *,
    last_ingestion: datetime | None = None,
    last_query: datetime | None = None,
) -> None:
    err = try_sync_project(
        wiki_name,
        wiki_root,
        last_ingestion=last_ingestion,
        last_query=last_query,
    )
    if err:
        click.echo(f"Project sync warning: {err}", err=True)


def _format_project_row(record) -> str:
    flags: list[str] = []
    if record.on_disk:
        flags.append("disk")
    if record.in_oracle:
        flags.append("oracle")
    flag_str = ",".join(flags) if flags else "-"

    def _ts(value: datetime | None) -> str:
        return value.strftime("%Y-%m-%d %H:%M") if value else "-"

    return (
        f"{record.name}\t"
        f"pages={record.page_count}\tsources={record.source_count}\t"
        f"embeddings={record.embedding_count}\t"
        f"ingested={_ts(record.last_ingestion)}\t"
        f"queried={_ts(record.last_query)}\t"
        f"[{flag_str}]"
    )


@click.group()
@click.option(
    "--wikis-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_WIKIS_DIR,
    show_default=True,
    help="Parent directory containing wiki projects.",
)
@click.pass_context
def cli(ctx: click.Context, wikis_dir: Path) -> None:
    ctx.ensure_object(dict)
    ctx.obj["wikis_dir"] = wikis_dir


@cli.command("create-wiki")
@click.argument("name")
@click.option(
    "--generate-schema",
    "should_generate_schema",
    is_flag=True,
    help="Generate SCHEMA.md with the LLM after scaffolding.",
)
@click.option(
    "--domain",
    default=None,
    help="Wiki topic description (required with --generate-schema).",
)
@click.option(
    "--link-style",
    type=click.Choice(["wikilink", "markdown"], case_sensitive=False),
    default="wikilink",
    show_default=True,
    help="Cross-reference style recorded in SCHEMA.md.",
)
@click.pass_context
def create_wiki_cmd(
    ctx: click.Context,
    name: str,
    should_generate_schema: bool,
    domain: str | None,
    link_style: str,
) -> None:
    """Create a new wiki directory tree."""
    wikis_dir: Path = ctx.obj["wikis_dir"]

    if should_generate_schema and not domain:
        raise click.UsageError("--domain is required when using --generate-schema")

    try:
        wiki_root = create_wiki(name, wikis_dir)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="NAME") from exc
    except WikiExistsError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Created wiki: {wiki_root}")

    _sync_project_quiet(name, wiki_root)

    if should_generate_schema:
        try:
            schema_path = generate_schema(
                wiki_root,
                domain=domain or "",
                link_style=link_style,
            )
        except (SchemaGenerationError, FileNotFoundError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"Generated schema: {schema_path}")


@cli.command("list-wikis")
@click.pass_context
def list_wikis_cmd(ctx: click.Context) -> None:
    """List wiki projects under the wikis directory."""
    wikis_dir: Path = ctx.obj["wikis_dir"]
    wikis = list_wikis(wikis_dir)

    if not wikis:
        click.echo(f"No wikis found in {wikis_dir.resolve()}")
        return

    for wiki_root in wikis:
        click.echo(f"{wiki_root.name}\t{wiki_root}")


@cli.command("inspect-wiki")
@click.argument("name")
@click.pass_context
def inspect_wiki_cmd(ctx: click.Context, name: str) -> None:
    """Show wiki structure, schema summary, frontmatter status, and links."""
    wikis_dir: Path = ctx.obj["wikis_dir"]

    try:
        validate_wiki_name(name)
        report = inspect_wiki(name, wikis_dir)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="NAME") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Wiki: {report.name}")
    click.echo(f"Path: {report.path}")
    click.echo("")
    click.echo("Directories:")

    for subdir in ("raw", "summaries", "entities", "topics"):
        count = report.directory_counts.get(subdir, 0)
        label = "sources" if subdir == "raw" else "pages"
        click.echo(f"  {subdir + '/':13} {count} {label}")

    click.echo("")
    if report.schema_path:
        size = report.schema_path.stat().st_size
        click.echo(f"Schema: {report.schema_path} ({size:,} chars)")
        if report.schema_preview:
            click.echo(f"  First heading: {report.schema_preview}")
    else:
        click.echo("Schema: not found")

    click.echo("")
    click.echo("Frontmatter:")
    click.echo(f"  Valid pages:   {report.valid_pages}")
    click.echo(f"  Invalid pages: {len(report.invalid_pages)}")

    for page_path, errors in report.invalid_pages:
        click.echo(f"    {page_path}:")
        for error in errors:
            click.echo(f"      - {error}")

    click.echo("")
    click.echo("Links:")
    if not report.links:
        click.echo("  (none found)")
    else:
        for link in report.links:
            if link.resolved:
                click.echo(f"  [[{link.target}]]  ->  {link.resolved}  (from {link.source_page})")
            else:
                click.echo(f"  [[{link.target}]]  ->  NOT FOUND  (from {link.source_page})")


@cli.command("ingest")
@click.argument("wiki_name")
@click.argument("source_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def ingest_cmd(ctx: click.Context, wiki_name: str, source_path: Path) -> None:
    """Ingest a source file into a wiki (copies to raw/, updates wiki pages)."""
    wikis_dir: Path = ctx.obj["wikis_dir"]

    try:
        validate_wiki_name(wiki_name)
        result = run_ingestion(wiki_name, source_path, wikis_dir=wikis_dir)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="WIKI_NAME") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc

    errors = result.get("errors", [])
    if errors:
        for error in errors:
            click.echo(f"Error: {error}", err=True)
        raise click.ClickException("Ingestion failed.")

    click.echo(f"Ingested: {result.get('source_title') or source_path.name}")
    click.echo(f"Raw source: {result.get('source_path')}")

    pages = result.get("pages_written", [])
    click.echo(f"Pages written/updated: {len(pages)}")
    for page in pages:
        click.echo(f"  - {page}")

    contradictions = result.get("contradictions", [])
    if contradictions:
        click.echo(f"Contradictions flagged: {len(contradictions)}")
        for item in contradictions:
            click.echo(f"  - {item.get('page')}: {item.get('note')}")

    gaps = result.get("gaps_flagged", [])
    if gaps:
        click.echo(f"Gap stubs created: {len(gaps)}")
        for gap in gaps:
            click.echo(f"  - {gap}")

    embed_embedded = result.get("embed_embedded", 0)
    embed_skipped = result.get("embed_skipped", 0)
    if embed_embedded or embed_skipped:
        click.echo(f"Embeddings synced: {embed_embedded} embedded, {embed_skipped} skipped")

    embed_warnings = result.get("embed_warnings") or []
    for warning in embed_warnings:
        click.echo(f"Embed warning: {warning}", err=True)

    wiki_root = resolve_wiki_root(wikis_dir, wiki_name)
    _sync_project_quiet(wiki_name, wiki_root, last_ingestion=datetime.now())


@cli.command("list-projects")
@click.pass_context
def list_projects_cmd(ctx: click.Context) -> None:
    """List wiki projects (disk + Oracle metadata)."""
    wikis_dir: Path = ctx.obj["wikis_dir"]
    try:
        projects = list_all_projects(wikis_dir)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    if not projects:
        click.echo(f"No projects found under {wikis_dir.resolve()}")
        return

    for record in projects:
        click.echo(_format_project_row(record))


@cli.command("sync-project")
@click.argument("wiki_name")
@click.pass_context
def sync_project_cmd(ctx: click.Context, wiki_name: str) -> None:
    """Refresh Oracle wiki_projects metadata from disk."""
    wiki_root = _resolve_wiki(ctx, wiki_name)
    try:
        record = sync_project_metadata(wiki_name, wiki_root)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Synced: {record.name}")
    click.echo(_format_project_row(record))


@cli.command("lint")
@click.argument("wiki_name")
@click.option(
    "--checks",
    type=click.Choice(["structural", "llm", "all"], case_sensitive=False),
    default="structural",
    show_default=True,
    help="Check set: structural (7.1), llm (7.2), or all.",
)
@click.option("--report-only", is_flag=True, help="Print report only; do not offer fixes.")
@click.option("--no-fix-prompt", is_flag=True, help="Skip interactive fix prompts.")
@click.option("--auto-fix", is_flag=True, help="Apply all auto-fixable issues without prompting.")
@click.pass_context
def lint_cmd(
    ctx: click.Context,
    wiki_name: str,
    checks: str,
    report_only: bool,
    no_fix_prompt: bool,
    auto_fix: bool,
) -> None:
    """Health-check a wiki, report issues, and optionally apply fixes."""
    wikis_dir: Path = ctx.obj["wikis_dir"]
    try:
        result = run_lint(wiki_name, wikis_dir=wikis_dir, checks=checks)
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="WIKI_NAME") from exc

    for error in result.get("errors") or []:
        click.echo(f"Lint warning: {error}", err=True)

    issues = list(result.get("issues") or [])
    click.echo(
        format_lint_report(
            issues,
            wiki_name=wiki_name,
            research_questions=result.get("research_questions"),
            source_suggestions=result.get("source_suggestions"),
        )
    )

    wiki_root = _resolve_wiki(ctx, wiki_name)
    project_name = str(result.get("project_name") or wiki_name)
    schema_text = str(result.get("schema_text") or "")

    skip_fixes = report_only or no_fix_prompt
    fixable = [issue for issue in issues if issue.auto_fixable]

    if skip_fixes or not fixable:
        finalize_wiki_changes(
            wiki_root,
            project_name,
            [],
            issue_count=len(issues),
            fixes_applied=0,
        )
        return

    pages_touched: list[str] = []
    fixes_applied = 0
    fix_kinds: list[str] = []
    fixed_targets: set[str] = set()

    for issue in fixable:
        if should_skip_issue(issue, fixed_targets):
            continue

        click.echo("")
        pages = ", ".join(f"`{p}`" for p in issue.pages) if issue.pages else "(none)"
        click.echo(f"[{issue.check_type.value}] {pages}")
        click.echo(f"  {preview_fix(issue)}")

        if auto_fix:
            accept = True
        else:
            accept = click.confirm("Apply this fix?", default=False)

        if not accept:
            continue

        try:
            fix_result = apply_fix(wiki_root, issue, schema_text=schema_text)
        except Exception as exc:
            click.echo(f"Fix failed: {exc}", err=True)
            continue

        if fix_result.applied:
            fixes_applied += 1
            fix_kinds.append(issue.fix_kind.value)
            pages_touched.extend(fix_result.pages_touched)
            if issue.target and issue.fix_kind.value == "create_stub":
                fixed_targets.add(issue.target.strip().lower())
            click.echo(fix_result.message)
        else:
            click.echo(fix_result.message or "Fix was not applied.")

    finalize_wiki_changes(
        wiki_root,
        project_name,
        pages_touched,
        issue_count=len(issues),
        fixes_applied=fixes_applied,
        fix_kinds=fix_kinds,
    )
    if fixes_applied:
        click.echo(f"\nApplied {fixes_applied} fix(es).")


def _resolve_wiki(ctx: click.Context, name: str) -> Path:
    wikis_dir: Path = ctx.obj["wikis_dir"]
    try:
        validate_wiki_name(name)
        return resolve_wiki_root(wikis_dir, name)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="WIKI_NAME") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc


@cli.command("show-index")
@click.argument("wiki_name")
@click.pass_context
def show_index_cmd(ctx: click.Context, wiki_name: str) -> None:
    """Print the wiki index and page counts."""
    wiki_root = _resolve_wiki(ctx, wiki_name)
    stats = get_index_stats(wiki_root)
    click.echo(f"Wiki: {wiki_name} ({stats['total']} pages)")
    click.echo("")
    click.echo(read_index(wiki_root).rstrip())


@cli.command("show-log")
@click.argument("wiki_name")
@click.option("--tail", default=0, show_default=False, help="Show only the last N entries.")
@click.pass_context
def show_log_cmd(ctx: click.Context, wiki_name: str, tail: int) -> None:
    """Print the wiki activity log."""
    wiki_root = _resolve_wiki(ctx, wiki_name)
    if tail > 0:
        content = read_log_tail(wiki_root, tail)
    else:
        content = read_log(wiki_root)
    click.echo(content.rstrip())


@cli.command("rebuild-index")
@click.argument("wiki_name")
@click.pass_context
def rebuild_index_cmd(ctx: click.Context, wiki_name: str) -> None:
    """Rebuild index.md from page frontmatter (no LLM calls)."""
    wiki_root = _resolve_wiki(ctx, wiki_name)
    index_path = rebuild_index(wiki_root)
    stats = get_index_stats(wiki_root)
    append_log_entry(
        wiki_root,
        LOG_EVENT_INDEX_REBUILD,
        f"{stats['total']} pages indexed",
    )
    click.echo(f"Rebuilt: {index_path}")
    click.echo(
        f"  sources={stats['summary']} entities={stats['entity']} "
        f"concepts={stats['concept']} overviews={stats['overview']}"
    )


@cli.command("db-ping")
def db_ping_cmd() -> None:
    """Verify Oracle Database connectivity."""
    try:
        result = ping_oracle()
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Oracle OK: {result}")


@cli.command("db-init")
@click.option("--rebuild-indexes", is_flag=True, help="Drop and recreate vector/FTS indexes.")
def db_init_cmd(rebuild_indexes: bool) -> None:
    """Create wiki_pages and wiki_projects tables in Oracle."""
    try:
        actions = ensure_schema(force_rebuild_indexes=rebuild_indexes)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    for action in actions:
        click.echo(action)


@cli.command("db-status")
@click.argument("wiki_name")
@click.pass_context
def db_status_cmd(ctx: click.Context, wiki_name: str) -> None:
    """Compare disk page count with Oracle embedding row count."""
    wiki_root = _resolve_wiki(ctx, wiki_name)
    disk_count = len(iter_content_pages(wiki_root))
    try:
        db_count = count_project_pages(wiki_name)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Wiki: {wiki_name}")
    click.echo(f"  Disk pages:   {disk_count}")
    click.echo(f"  Oracle rows:  {db_count}")
    if disk_count == db_count:
        click.echo("  Status: in sync")
    else:
        click.echo("  Status: out of sync (run embed-wiki)")


@cli.command("embed-wiki")
@click.argument("wiki_name")
@click.option("--force", is_flag=True, help="Re-embed all pages even if content_hash unchanged.")
@click.option("--prune", is_flag=True, help="Delete Oracle rows for pages removed from disk.")
@click.pass_context
def embed_wiki_cmd(ctx: click.Context, wiki_name: str, force: bool, prune: bool) -> None:
    """Embed all wiki pages and store in Oracle."""
    wiki_root = _resolve_wiki(ctx, wiki_name)
    try:
        stats = sync_wiki(wiki_name, wiki_root, force=force, prune=prune)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(
        f"Embedded: {stats.embedded}, skipped: {stats.skipped}, deleted: {stats.deleted}"
    )
    for error in stats.errors or []:
        click.echo(f"Error: {error}", err=True)

    append_log_entry(
        wiki_root,
        LOG_EVENT_EMBED_SYNC,
        f"{stats.embedded} embedded, {stats.skipped} skipped"
        + (f", {stats.deleted} pruned" if stats.deleted else ""),
    )
    _sync_project_quiet(wiki_name, wiki_root)


@cli.command("search")
@click.argument("wiki_name")
@click.argument("query")
@click.option("--top-k", default=10, show_default=True, help="Number of results.")
@click.option(
    "--mode",
    type=click.Choice(["hybrid", "vector", "fts"], case_sensitive=False),
    default="hybrid",
    show_default=True,
)
@click.option("--type", "page_type", default=None, help="Filter by page type.")
@click.pass_context
def search_cmd(
    ctx: click.Context,
    wiki_name: str,
    query: str,
    top_k: int,
    mode: str,
    page_type: str | None,
) -> None:
    """Hybrid/vector/full-text search over embedded wiki pages."""
    _resolve_wiki(ctx, wiki_name)
    try:
        if mode == "vector":
            from llm_wiki.search.vector import vector_search

            results = vector_search(wiki_name, query, top_k=top_k, page_type=page_type)
        elif mode == "fts":
            from llm_wiki.search.fts import fts_search

            results = fts_search(wiki_name, query, top_k=top_k, page_type=page_type)
        else:
            results = hybrid_search(wiki_name, query, top_k=top_k, page_type=page_type)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    if not results:
        click.echo("No results.")
        return

    for index, item in enumerate(results, start=1):
        score_bits: list[str] = []
        if item.rrf_score:
            score_bits.append(f"rrf={item.rrf_score:.4f}")
        if item.vector_score is not None:
            score_bits.append(f"vec={item.vector_score:.3f}")
        if item.fts_score is not None:
            score_bits.append(f"fts={item.fts_score:.1f}")
        scores = f" ({', '.join(score_bits)})" if score_bits else ""
        click.echo(f"{index}. [[{item.title}]] `{item.page_path}`{scores}")
        if item.snippet:
            click.echo(f"   {item.snippet}")


def _print_query_result(result: dict) -> None:
    errors = result.get("errors") or []
    if errors:
        for error in errors:
            click.echo(f"Error: {error}", err=True)
        raise click.ClickException("Query failed.")

    answer = result.get("answer", "")
    coverage = result.get("coverage", "")
    pages_used = result.get("pages_used") or []

    click.echo(answer.rstrip())
    click.echo("")
    click.echo(f"Coverage: {coverage}")
    if pages_used:
        click.echo(f"Pages used: {', '.join(f'[[{t}]]' for t in pages_used)}")


def _maybe_save_answer(
    ctx: click.Context,
    wiki_name: str,
    result: dict,
    *,
    auto_save: bool,
    no_save_prompt: bool,
) -> None:
    if no_save_prompt or not result.get("answer"):
        return

    title = (result.get("suggested_title") or result.get("question", "Query answer")).strip()
    if len(title) > 120:
        title = title[:117] + "..."

    if auto_save:
        save = True
    else:
        save = click.confirm(f"Save this answer as wiki page '{title}'?", default=False)

    if not save:
        return

    wiki_root = _resolve_wiki(ctx, wiki_name)
    try:
        page_path = save_answer_as_page(
            wiki_root,
            wiki_name,
            title=title,
            body=str(result.get("answer", "")),
        )
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Saved: {page_path.relative_to(wiki_root)}")


@cli.command("query")
@click.argument("wiki_name")
@click.argument("question")
@click.option("--top-k", default=8, show_default=True, help="Pages to retrieve and read.")
@click.option("--save", "auto_save", is_flag=True, help="Save answer as wiki page without prompting.")
@click.option("--no-save-prompt", is_flag=True, help="Skip save prompt after answer.")
@click.pass_context
def query_cmd(
    ctx: click.Context,
    wiki_name: str,
    question: str,
    top_k: int,
    auto_save: bool,
    no_save_prompt: bool,
) -> None:
    """Ask the wiki a question and get a cited answer."""
    try:
        validate_wiki_name(wiki_name)
        result = run_query(wiki_name, question, wikis_dir=ctx.obj["wikis_dir"], top_k=top_k)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="WIKI_NAME") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc

    _print_query_result(result)
    wiki_root = _resolve_wiki(ctx, wiki_name)
    _sync_project_quiet(wiki_name, wiki_root, last_query=datetime.now())
    _maybe_save_answer(ctx, wiki_name, result, auto_save=auto_save, no_save_prompt=no_save_prompt)


@cli.command("chat")
@click.argument("wiki_name")
@click.option("--top-k", default=8, show_default=True)
@click.pass_context
def chat_cmd(ctx: click.Context, wiki_name: str, top_k: int) -> None:
    """Interactive Q&A session with follow-up questions."""
    try:
        validate_wiki_name(wiki_name)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="WIKI_NAME") from exc

    click.echo(f"Wiki chat: {wiki_name} (empty line or Ctrl+C to exit)")
    messages: list[dict[str, str]] = []

    while True:
        try:
            question = click.prompt("\nYou", prompt_suffix="> ")
        except (click.Abort, EOFError):
            click.echo("\nBye.")
            break

        question = question.strip()
        if not question:
            click.echo("Bye.")
            break

        try:
            result = run_query(
                wiki_name,
                question,
                wikis_dir=ctx.obj["wikis_dir"],
                messages=messages,
                top_k=top_k,
            )
        except FileNotFoundError as exc:
            raise click.ClickException(str(exc)) from exc

        try:
            _print_query_result(result)
        except click.ClickException:
            continue

        messages = list(result.get("messages") or messages)
        wiki_root = _resolve_wiki(ctx, wiki_name)
        _sync_project_quiet(wiki_name, wiki_root, last_query=datetime.now())
        _maybe_save_answer(ctx, wiki_name, result, auto_save=False, no_save_prompt=False)


if __name__ == "__main__":
    cli()

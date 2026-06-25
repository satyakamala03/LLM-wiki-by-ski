"""Wiki filesystem scaffolding and inspection (Phase 1, Step 1)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from llm_wiki.wiki.frontmatter import parse_page, validate_frontmatter

WIKI_SUBDIRS = ("raw", "summaries", "entities", "topics")
CONTENT_DIRS = ("summaries", "entities", "topics")
WIKI_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
WIKILINK_PATTERN = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")

SCHEMA_STUB = "# Wiki Schema\n\nSchema will be generated in setup step 2.\n"
INDEX_STUB = "# Wiki Index\n"
LOG_STUB = "# Wiki Log\n"


class WikiExistsError(FileExistsError):
    """Raised when create_wiki is called for an existing wiki directory."""


@dataclass
class WikiLinkRef:
    source_page: Path
    target: str
    resolved: Path | None


@dataclass
class WikiInspection:
    name: str
    path: Path
    directory_counts: dict[str, int] = field(default_factory=dict)
    schema_path: Path | None = None
    schema_preview: str = ""
    valid_pages: int = 0
    invalid_pages: list[tuple[Path, list[str]]] = field(default_factory=list)
    links: list[WikiLinkRef] = field(default_factory=list)


def validate_wiki_name(name: str) -> str:
    name = name.strip()
    if not name or not WIKI_NAME_PATTERN.fullmatch(name):
        raise ValueError(
            "Wiki name must use lowercase letters, numbers, and hyphens only "
            '(e.g. "eggless-baking").'
        )
    return name


def is_wiki_root(path: Path) -> bool:
    if not path.is_dir():
        return False
    for subdir in WIKI_SUBDIRS:
        if not (path / subdir).is_dir():
            return False
    return (path / "SCHEMA.md").is_file()


def create_wiki(name: str, path: Path | str) -> Path:
    """Scaffold a new wiki directory tree at path/name.

    Creates raw/, summaries/, entities/, topics/ plus placeholder SCHEMA.md,
    index.md, and log.md. Raises WikiExistsError if the wiki already exists.
    """
    wiki_name = validate_wiki_name(name)
    parent = Path(path)
    wiki_root = (parent / wiki_name).resolve()

    if wiki_root.exists():
        raise WikiExistsError(f"Wiki already exists: {wiki_root}")

    parent.mkdir(parents=True, exist_ok=True)

    for subdir in WIKI_SUBDIRS:
        (wiki_root / subdir).mkdir(parents=True, exist_ok=False)

    (wiki_root / "SCHEMA.md").write_text(SCHEMA_STUB, encoding="utf-8")
    (wiki_root / "index.md").write_text(INDEX_STUB, encoding="utf-8")
    (wiki_root / "log.md").write_text(LOG_STUB, encoding="utf-8")

    return wiki_root


def list_wikis(wikis_dir: Path | str) -> list[Path]:
    """Return sorted wiki root paths under wikis_dir."""
    wikis_dir = Path(wikis_dir)
    if not wikis_dir.is_dir():
        return []

    wikis = [p for p in wikis_dir.iterdir() if p.is_dir() and is_wiki_root(p)]
    return sorted(wikis, key=lambda p: p.name)


def title_to_slug(title: str) -> str:
    slug = title.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def iter_content_pages(wiki_root: Path) -> list[Path]:
    pages: list[Path] = []
    for subdir in CONTENT_DIRS:
        directory = wiki_root / subdir
        if directory.is_dir():
            pages.extend(sorted(directory.glob("*.md")))
    return pages


def build_title_index(wiki_root: Path) -> dict[str, Path]:
    """Map lowercased page title -> path."""
    index: dict[str, Path] = {}
    for page_path in iter_content_pages(wiki_root):
        try:
            meta, _ = parse_page(page_path)
        except Exception:
            continue
        title = meta.get("title")
        if isinstance(title, str) and title.strip():
            index[title.strip().lower()] = page_path
    return index


def find_wikilinks(body: str) -> list[str]:
    return [match.group(1).strip() for match in WIKILINK_PATTERN.finditer(body)]


def resolve_wikilink(wiki_root: Path, target: str, title_index: dict[str, Path] | None = None) -> Path | None:
    """Resolve [[Page Title]] to a file path under the wiki."""
    title_index = title_index or build_title_index(wiki_root)
    normalized = target.strip().lower()
    if normalized in title_index:
        return title_index[normalized]

    slug = title_to_slug(target)
    if not slug:
        return None

    for subdir in CONTENT_DIRS:
        candidate = wiki_root / subdir / f"{slug}.md"
        if candidate.is_file():
            return candidate
    return None


def inspect_wiki(name: str, wikis_dir: Path | str) -> WikiInspection:
    """Collect structure, frontmatter, and link info for a wiki."""
    wiki_name = validate_wiki_name(name)
    wiki_root = (Path(wikis_dir) / wiki_name).resolve()

    if not is_wiki_root(wiki_root):
        raise FileNotFoundError(f"Wiki not found: {wiki_root}")

    directory_counts: dict[str, int] = {}
    for subdir in WIKI_SUBDIRS:
        directory = wiki_root / subdir
        if directory.is_dir():
            directory_counts[subdir] = len(list(directory.glob("*")))
        else:
            directory_counts[subdir] = 0

    schema_path = wiki_root / "SCHEMA.md"
    schema_text = schema_path.read_text(encoding="utf-8") if schema_path.is_file() else ""
    schema_preview = ""
    for line in schema_text.splitlines():
        if line.strip():
            schema_preview = line.strip()
            break

    valid_pages = 0
    invalid_pages: list[tuple[Path, list[str]]] = []
    title_index = build_title_index(wiki_root)

    links: list[WikiLinkRef] = []
    seen_links: set[tuple[str, str]] = set()

    for page_path in iter_content_pages(wiki_root):
        try:
            meta, body = parse_page(page_path)
        except Exception as exc:
            invalid_pages.append((page_path, [f"Could not parse frontmatter: {exc}"]))
            continue

        errors = validate_frontmatter(meta)
        if errors:
            invalid_pages.append((page_path, errors))
        else:
            valid_pages += 1

        for target in find_wikilinks(body):
            key = (str(page_path.relative_to(wiki_root)), target)
            if key in seen_links:
                continue
            seen_links.add(key)
            resolved = resolve_wikilink(wiki_root, target, title_index)
            links.append(
                WikiLinkRef(
                    source_page=page_path.relative_to(wiki_root),
                    target=target,
                    resolved=resolved.relative_to(wiki_root) if resolved else None,
                )
            )

    return WikiInspection(
        name=wiki_name,
        path=wiki_root,
        directory_counts=directory_counts,
        schema_path=schema_path if schema_path.is_file() else None,
        schema_preview=schema_preview,
        valid_pages=valid_pages,
        invalid_pages=invalid_pages,
        links=links,
    )

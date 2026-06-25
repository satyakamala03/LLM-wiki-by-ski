Write or update a wiki overview page body in markdown.

Wiki schema:
{schema_text}

Overview topic: {title}
Source filename: {source_filename}
New information from this source:
{new_info}

Existing page content (empty if new page):
{existing_body}

Requirements:
- Return ONLY markdown body content (no YAML frontmatter)
- Start with `# {title}`
- Synthesize how this source fits the broader topic
- Merge with existing content when present
- Link to related entities and concepts with wikilinks
- Do not invent facts

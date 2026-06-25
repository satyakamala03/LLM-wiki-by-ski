Write or update a wiki concept page body in markdown.

Wiki schema:
{schema_text}

Concept name: {title}
Source filename: {source_filename}
New information from this source:
{new_info}

Existing page content (empty if new page):
{existing_body}

Requirements:
- Return ONLY markdown body content (no YAML frontmatter)
- Start with `# {title}`
- Explain the concept clearly using facts from the source
- Merge with existing content when present
- Use wikilinks where helpful
- Do not invent facts

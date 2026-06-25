Write or update a wiki entity page body in markdown.

Wiki schema:
{schema_text}

Entity name: {title}
Source filename: {source_filename}
New information from this source:
{new_info}

Existing page content (empty if new page):
{existing_body}

Requirements:
- Return ONLY markdown body content (no YAML frontmatter)
- Start with `# {title}`
- Merge new facts into the page without deleting useful existing content
- Use wikilinks to related pages where helpful
- Do not invent facts not supported by the source text or existing page
- If this is a new page, write a concise but useful starter page

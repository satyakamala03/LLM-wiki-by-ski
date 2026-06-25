Write a wiki summary page body in markdown for one ingested source.

Wiki schema:
{schema_text}

Source filename: {source_filename}
Source title: {source_title}
Source text:
{source_text}

Extracted entities: {entities}
Extracted concepts: {concepts}

Requirements:
- Return ONLY markdown body content (no YAML frontmatter)
- Start with one `#` heading for the summary title
- Capture key points faithfully; do not hallucinate
- Link important entities and concepts using wikilinks like [[Aquafaba]]
- Include a short `## Key takeaways` section with bullet points
- Include a `## Source` section noting the raw filename

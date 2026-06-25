Create a short stub wiki page body for a topic mentioned in a source but not yet covered.

Wiki schema:
{schema_text}

Name: {title}
Kind: {kind}
Source filename: {source_filename}
Mention context from source:
{context}

Requirements:
- Return ONLY markdown body content (no YAML frontmatter)
- Start with `# {title}`
- Explain that this page is a stub created because the topic was mentioned in the source
- Include what the source said (briefly)
- Add `## Needs expansion` with 2-3 bullets for future work

A wiki page may contain claims that newer source summaries have revised or superseded.

Wiki schema excerpt:
{schema_excerpt}

Page — `{page_path}` ({page_title}, updated {page_updated}):
{page_body}

Related source summaries (often newer per-source distillations):
{summaries_block}

Return ONLY valid JSON:
{{
  "has_stale_claim": true,
  "note": "What is outdated and why",
  "stale_claim": "The outdated assertion on the page",
  "superseded_by": "Which summary or source perspective replaces it",
  "suggested_action": "Revise the page body or add a Contradictions note"
}}

If the page is still accurate relative to these summaries:
{{
  "has_stale_claim": false,
  "note": "",
  "stale_claim": "",
  "superseded_by": "",
  "suggested_action": ""
}}

Rules:
- Only flag when a summary clearly updates or contradicts the page's main claims
- Do not invent facts not in the provided texts

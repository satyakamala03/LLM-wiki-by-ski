Compare two wiki pages for contradictory or incompatible factual claims.

Wiki schema excerpt:
{schema_excerpt}

Page A — `{page_a_path}` ({page_a_title}):
{page_a_body}

Page B — `{page_b_path}` ({page_b_title}):
{page_b_body}

Return ONLY valid JSON:
{{
  "has_contradiction": true,
  "note": "One or two sentences describing the disagreement factually",
  "suggested_action": "Concrete next step (e.g. add Contradictions section, revise one page)"
}}

If the pages are compatible or discuss different aspects without conflict:
{{
  "has_contradiction": false,
  "note": "",
  "suggested_action": ""
}}

Rules:
- Only flag genuine factual tension, not mere different emphasis
- Do not invent claims not present in the page bodies
- Ignore unresolved ## Contradictions sections as already-noted unless the main body still contradicts

Compare a new claim from a source against an existing wiki page.

Wiki page title: {page_title}
Existing page content:
{existing_body}

New claim from source `{source_filename}`:
{claim}

If the new claim contradicts or tensionally disagrees with the existing page, return JSON:
{{
  "has_contradiction": true,
  "note": "One or two sentences describing the disagreement, citing both perspectives factually"
}}

Otherwise return:
{{
  "has_contradiction": false,
  "note": ""
}}

Return ONLY valid JSON. Do not invent contradictions.

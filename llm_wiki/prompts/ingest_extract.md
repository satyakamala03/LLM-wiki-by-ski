Read the source article and extract structured information for a wiki.

Wiki schema (follow these conventions):
{schema_text}

Source filename: {source_filename}
Source text:
{source_text}

Return ONLY valid JSON with this shape:
{{
  "source_title": "short human-readable title for this source",
  "entities": [
    {{"name": "Aquafaba", "description": "one sentence from the source", "tags": ["vegan", "foaming"]}}
  ],
  "concepts": [
    {{"name": "Emulsification", "description": "one sentence from the source", "tags": ["technique"]}}
  ],
  "overviews": [
    {{"name": "Egg Substitutes Comparison", "description": "why this overview matters", "tags": ["overview"]}}
  ],
  "key_claims": [
    "Specific factual claim stated in the source"
  ],
  "mentioned_without_pages": [
    "Names mentioned in the source that may need a page later"
  ]
}}

Rules:
- entities = specific ingredients, products, brands, people, dishes
- concepts = ideas, techniques, principles (not a single product)
- overviews = broad synthesis topics this source contributes to (0-2 items)
- Do not invent facts not present in the source
- Keep lists concise but useful

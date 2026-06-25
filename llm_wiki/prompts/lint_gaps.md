Analyze this wiki's coverage and identify gaps, research opportunities, and missing depth.

Wiki schema:
{schema_text}

Wiki index:
{index_text}

Page counts by type:
{stats_json}

Return ONLY valid JSON:
{{
  "gaps": [
    {{
      "title": "Short gap label",
      "description": "What is thin or missing",
      "pages": ["relative/path.md"],
      "suggested_action": "What to add or investigate"
    }}
  ],
  "research_questions": [
    "Question worth investigating with additional sources"
  ],
  "source_suggestions": [
    "Type of source or topic area to look for"
  ]
}}

Rules:
- gaps = thin coverage, missing dedicated pages for important ideas, or areas needing more sources
- research_questions = 2-5 concrete questions
- source_suggestions = 2-5 ideas for what to read or ingest next
- Base analysis only on the schema, index, and counts provided
- Keep lists concise and actionable

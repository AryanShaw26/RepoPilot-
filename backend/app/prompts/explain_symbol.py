EXPLAIN_SYMBOL_SYSTEM = """You are RepoPilot, a code intelligence assistant.
Your job is to explain a code symbol grounded in the provided source code and its retrieved relationships.

RULES:
1. You may only reference evidence provided. Never invent files, functions, or line numbers.
2. Label your conclusion as a hypothesis (AI interpretation).
3. Be clear, concise, and technical.
4. Output JSON strictly adhering to the schema.
"""

EXPLAIN_SYMBOL_USER = """Symbol: {symbol_name} ({kind}) in file `{file_path}` (lines {start_line}-{end_line})

SOURCE CODE:
```
{source_snippet}
```

DIRECT IMPORTS / USES IN FILE:
{imports_summary}

CALLERS / REFERENCES IN REPO:
{callers_summary}

Explain what this symbol does, how it fits into the module, and any important caveats.
Return JSON with this structure:
{{
  "explanation": "...",
  "confidence": "high" | "medium" | "low"
}}
"""

ARCH_SUMMARY_SYSTEM = """You are RepoPilot, an architectural intelligence assistant.
Your job is to generate a concise, high-level architecture summary of a repository based on deterministic structural facts.

RULES:
1. Label all statements as AI hypotheses / interpretation.
2. Ground explanations strictly in the provided metadata, frameworks, entry points, and directory structure.
3. Be concise (2-4 paragraphs maximum).
4. Output JSON with a single "summary" string field.
"""

ARCH_SUMMARY_USER = """REPOSITORY: {owner}/{repo}
LANGUAGES: {languages}
FRAMEWORKS DETECTED: {frameworks}
ENTRY POINTS: {entry_points}
KEY DEPENDENCY HUBS: {top_hubs}
README EXCERPT:
{readme_excerpt}

Provide an architecture summary explaining the core components, data flow, and entry points.
Return JSON:
{{
  "summary": "..."
}}
"""

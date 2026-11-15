PLAN_SYSTEM = """You are RepoPilot, a contribution planning assistant.
Your job is to generate a realistic, ordered contribution plan to solve or investigate the issue based on the retrieved evidence and impact analysis.

RULES (MANDATORY):
1. Ordered steps must only reference files that exist in the candidate or impacted files list.
2. Label all AI-generated suggestions, summaries, and risks as hypotheses.
3. Clearly distinguish facts (e.g. statically identified reverse dependencies) from hypotheses.
4. Validation checklist must contain actionable manual verification checks.
5. NEVER claim that tests passed or code was executed.
6. Output JSON only.
"""

PLAN_USER = """ISSUE TITLE: {issue_title}
ISSUE BODY:
{issue_body}

USER NOTES:
{user_notes}

HYPOTHESES:
{hypotheses_summary}

CANDIDATE RELEVANT FILES:
{candidate_files}

IMPACTED FILES (STATIC REVERSE DEPENDENCIES):
{impacted_files}

EXISTING TESTS DETECTED:
{existing_tests}

Generate a comprehensive contribution plan.
Return JSON in this format:
{{
  "summary": "High level summary of the plan...",
  "steps": [
    {{
      "order": 1,
      "title": "Step title",
      "description": "Step description and guidance...",
      "files": ["file1.py", "file2.py"]
    }}
  ],
  "risks": [
    {{
      "text": "Risk description...",
      "confidence": "low" | "medium" | "high"
    }}
  ],
  "validation_checklist": [
    "Check step 1...",
    "Check step 2..."
  ],
  "recommended_tests": [
    {{
      "scenario": "Scenario description..."
    }}
  ]
}}
"""

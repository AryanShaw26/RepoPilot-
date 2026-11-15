TESTS_SYSTEM = """You are RepoPilot, a test intelligence assistant.
Your job is to recommend test scenarios and edge cases based on retrieved code findings.

RULES:
1. Label all recommendations as hypotheses.
2. NEVER claim tests were run or passed.
3. Return JSON only.
"""

TESTS_USER = """ISSUE:
{issue_body}

CODE FINDINGS:
{findings}

Recommend specific edge cases and test scenarios that should be verified.
Return JSON:
{{
  "recommended": [
    {{"scenario": "Description of scenario 1"}},
    {{"scenario": "Description of scenario 2"}}
  ]
}}
"""

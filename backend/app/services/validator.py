from typing import Any, Dict, List, Set
from app.schemas.investigation import Hypothesis, RankedResult

CONSTANT_DISCLAIMER = (
    "AI-generated suggestions are hypotheses based on retrieved repository evidence. "
    "Verify before implementing. RepoPilot did not execute any code or tests."
)


def validate_hypotheses(
    hypotheses: List[Dict[str, Any]],
    valid_evidence_ids: Set[str],
) -> List[Hypothesis]:
    """
    Validates hypotheses:
    1. Every evidence_refs ID must exist in valid_evidence_ids; otherwise dropped.
    2. Hypotheses with zero valid refs are downgraded to confidence: "low" and unsupported: True.
    3. Forces kind: "hypothesis" on all items.
    """
    validated: List[Hypothesis] = []

    for idx, h in enumerate(hypotheses, 1):
        raw_refs = h.get("evidence_refs", [])
        cleaned_refs = [ref for ref in raw_refs if ref in valid_evidence_ids]

        confidence = h.get("confidence", "medium")
        unsupported = False

        if not cleaned_refs:
            confidence = "low"
            unsupported = True

        validated.append(
            Hypothesis(
                id=h.get("id", f"h{idx}"),
                text=h.get("text", ""),
                kind="hypothesis",
                confidence=confidence,
                evidence_refs=cleaned_refs,
                unsupported=unsupported,
            )
        )

    return validated


def validate_plan_steps(
    steps: List[Dict[str, Any]],
    valid_repo_file_paths: Set[str],
) -> List[Dict[str, Any]]:
    """
    Rule 3: Any file path mentioned in steps[].files must exist in repo_files; otherwise removed.
    Rule 4: Force kind: "hypothesis" on all steps.
    """
    validated_steps: List[Dict[str, Any]] = []

    for s in steps:
        raw_files = s.get("files", [])
        cleaned_files = [f for f in raw_files if f in valid_repo_file_paths]
        validated_steps.append({
            "order": s.get("order", len(validated_steps) + 1),
            "title": s.get("title", ""),
            "description": s.get("description", ""),
            "files": cleaned_files,
            "kind": "hypothesis",
        })

    return validated_steps


def validate_risks(risks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "text": r.get("text", ""),
            "kind": "hypothesis",
            "confidence": r.get("confidence", "low"),
        }
        for r in risks
    ]


def validate_recommended_tests(tests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "scenario": t.get("scenario", ""),
            "kind": "hypothesis",
        }
        for t in tests
    ]

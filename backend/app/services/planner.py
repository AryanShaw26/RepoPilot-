import posixpath
from typing import Any, Dict, List, Optional, Set
import uuid

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import logger
from app.db.models import ContributionPlan, Investigation, RepoFile
from app.prompts.plan import PLAN_SYSTEM, PLAN_USER
from app.schemas.plan import (
    ExistingTest,
    ImpactedFile,
    PlanContent,
    PlanResponse,
    PlanStep,
    RecommendedTest,
    RiskItem,
    TestRecommendations,
)
from app.services.graph import GraphService
from app.services.llm import LLMService
from app.services.test_intel import TestIntelService
from app.services.validator import (
    CONSTANT_DISCLAIMER,
    validate_plan_steps,
    validate_recommended_tests,
    validate_risks,
)


class LLMPlanOutput(BaseModel):
    summary: str
    steps: List[Dict[str, Any]] = []
    risks: List[Dict[str, Any]] = []
    validation_checklist: List[str] = []
    recommended_tests: List[Dict[str, Any]] = []


def render_plan_markdown(plan_data: Dict[str, Any]) -> str:
    summary_text = plan_data.get("summary", {}).get("text", "")
    steps = plan_data.get("steps", [])
    impacted = plan_data.get("impacted_files", [])
    risks = plan_data.get("risks", [])
    checklist = plan_data.get("validation_checklist", [])
    tests = plan_data.get("tests", {})
    existing_tests = tests.get("existing", [])
    rec_tests = tests.get("recommended", [])

    md_lines = [
        "# RepoPilot Contribution Plan",
        "",
        "> **Note:** " + CONSTANT_DISCLAIMER,
        "",
        "## Summary [Hypothesis]",
        summary_text,
        "",
        "## Ordered Contribution Steps",
    ]

    for s in steps:
        order = s.get("order", 1)
        title = s.get("title", "")
        desc = s.get("description", "")
        files = s.get("files", [])
        kind_tag = "[Fact]" if s.get("kind") == "fact" else "[Hypothesis]"
        md_lines.append(f"### {order}. {title} {kind_tag}")
        md_lines.append(desc)
        if files:
            files_formatted = ", ".join(f"`{f}`" for f in files)
            md_lines.append(f"- **Files:** {files_formatted}")
        md_lines.append("")

    md_lines.append("## Impacted Files [Verified]")
    if impacted:
        for imp in impacted:
            md_lines.append(f"- `{imp.get('path')}`: {imp.get('reason')} [Verified]")
    else:
        md_lines.append("No reverse dependencies detected.")
    md_lines.append("")

    md_lines.append("## Potential Risks & Considerations [Hypothesis]")
    if risks:
        for r in risks:
            conf = r.get("confidence", "low")
            md_lines.append(f"- {r.get('text')} *(confidence: {conf})* [Hypothesis]")
    else:
        md_lines.append("- Minimal blast radius identified.")
    md_lines.append("")

    md_lines.append("## Tests")
    md_lines.append("### Existing Tests [Verified]")
    if existing_tests:
        for et in existing_tests:
            md_lines.append(f"- `{et.get('path')}` (mapped via {et.get('method')}) [Verified]")
    else:
        md_lines.append("No existing test files directly mapped.")
    md_lines.append("")

    md_lines.append("### Recommended Test Scenarios [Hypothesis]")
    if rec_tests:
        for rt in rec_tests:
            md_lines.append(f"- {rt.get('scenario')} [Hypothesis]")
    else:
        md_lines.append("- Verify happy path and edge cases.")
    md_lines.append("")

    md_lines.append("## Manual Validation Checklist")
    for item in checklist:
        md_lines.append(f"- [ ] {item}")
    md_lines.append("")

    md_lines.append("---")
    md_lines.append(f"*{CONSTANT_DISCLAIMER}*")

    return "\n".join(md_lines)


class PlannerService:
    @staticmethod
    async def create_plan(
        db: AsyncSession,
        investigation_id: uuid.UUID,
        user_notes: Optional[str] = None,
    ) -> ContributionPlan:
        # Load investigation and results
        inv_stmt = (
            select(Investigation)
            .options(selectinload(Investigation.results))
            .where(Investigation.id == investigation_id)
        )
        inv_res = await db.execute(inv_stmt)
        inv = inv_res.scalar_one_or_none()
        if not inv:
            raise ValueError("Investigation not found")

        # 1. Deterministic facts first
        # Extract candidate files
        candidate_file_ids = [r.file_id for r in inv.results if r.file_id]

        # All repository files
        all_files_res = await db.execute(
            select(RepoFile.id, RepoFile.path).where(RepoFile.repository_id == inv.repository_id)
        )
        file_id_to_path = {fid: path for fid, path in all_files_res.all()}
        valid_repo_paths = set(file_id_to_path.values())

        candidate_file_paths = [file_id_to_path[fid] for fid in candidate_file_ids if fid in file_id_to_path]

        # Calculate static reverse dependencies (impacted files)
        impacted_files_data = await GraphService.reverse_dependencies(
            db, inv.repository_id, candidate_file_ids, depth=2
        )

        # Gather existing test mappings
        existing_tests: List[ExistingTest] = []
        seen_test_paths = set()
        for fpath in candidate_file_paths[:5]:
            tests_for_f = await TestIntelService.get_tests_for_file(db, inv.repository_id, fpath)
            for t in tests_for_f:
                if t.path not in seen_test_paths:
                    seen_test_paths.add(t.path)
                    existing_tests.append(t)

        # 2. LLM Step (or fallback)
        try:
            llm = LLMService()
            user_prompt = PLAN_USER.format(
                issue_title=inv.issue_title or "Untitled Issue",
                issue_body=inv.issue_body,
                user_notes=user_notes or "None provided.",
                hypotheses_summary=str(inv.hypotheses),
                candidate_files=", ".join(candidate_file_paths) or "None",
                impacted_files=", ".join(imp["path"] for imp in impacted_files_data) or "None",
                existing_tests=", ".join(t.path for t in existing_tests) or "None",
            )

            llm_plan: LLMPlanOutput = await llm.complete_json(
                system_prompt=PLAN_SYSTEM,
                user_prompt=user_prompt,
                schema_model=LLMPlanOutput,
            )

            validated_steps = validate_plan_steps(llm_plan.steps, valid_repo_paths)
            validated_risks = validate_risks(llm_plan.risks)
            validated_tests = validate_recommended_tests(llm_plan.recommended_tests)
            summary_dict = {"text": llm_plan.summary, "kind": "hypothesis"}
            checklist = llm_plan.validation_checklist or [
                "Locally verify changes against the issue description",
                "Ensure syntax and formatting passes lint checks",
            ]

        except Exception:
            logger.warning("LLM plan generation unavailable; using the deterministic fallback plan.")
            # Deterministic Fallback Plan
            summary_dict = {
                "text": "Deterministic initial plan based on identified candidate files and dependency graph.",
                "kind": "hypothesis",
            }
            validated_steps = []
            for idx, cpath in enumerate(candidate_file_paths[:4], 1):
                validated_steps.append({
                    "order": idx,
                    "title": f"Inspect and modify {posixpath.basename(cpath)}",
                    "description": f"Examine `{cpath}` regarding the issue.",
                    "files": [cpath],
                    "kind": "hypothesis",
                })
            validated_risks = [
                {
                    "text": "Modifications in core modules may impact dependent files.",
                    "kind": "hypothesis",
                    "confidence": "medium",
                }
            ]
            checklist = [
                "Reproduce the problem locally with minimal test case",
                "Review git diff against impacted dependencies",
            ]
            validated_tests = [
                {"scenario": "Test edge cases for affected code paths", "kind": "hypothesis"}
            ]

        plan_content = {
            "summary": summary_dict,
            "steps": validated_steps,
            "impacted_files": impacted_files_data,
            "risks": validated_risks,
            "validation_checklist": checklist,
            "tests": {
                "existing": [t.model_dump() for t in existing_tests],
                "recommended": validated_tests,
            },
            "disclaimer": CONSTANT_DISCLAIMER,
        }

        markdown = render_plan_markdown(plan_content)

        plan_record = ContributionPlan(
            investigation_id=investigation_id,
            user_notes=user_notes,
            plan=plan_content,
            markdown=markdown,
        )
        db.add(plan_record)
        await db.commit()
        await db.refresh(plan_record)
        return plan_record

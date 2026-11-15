import posixpath
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FileImport, RepoFile, TestMapping
from app.schemas.plan import ExistingTest, TestIntelOverview


class TestIntelService:
    @staticmethod
    async def compute_test_mappings(
        db: AsyncSession,
        repository_id: uuid.UUID,
    ) -> List[TestMapping]:
        """
        Computes deterministic mappings from source files to test files:
        1. Name convention (high confidence)
        2. Import analysis (high/medium confidence)
        3. Directory proximity (medium/low confidence)
        Persists to test_mappings table.
        """
        # Load all files
        files_res = await db.execute(
            select(RepoFile).where(RepoFile.repository_id == repository_id)
        )
        files = files_res.scalars().all()

        source_files: Dict[str, RepoFile] = {}
        test_files: Dict[str, RepoFile] = {}

        for f in files:
            if f.is_test:
                test_files[f.path] = f
            else:
                source_files[f.path] = f

        if not test_files or not source_files:
            return []

        # Load internal imports from test files -> source files
        test_file_ids = [tf.id for tf in test_files.values()]
        imports_res = await db.execute(
            select(FileImport.source_file_id, FileImport.target_file_id)
            .where(
                FileImport.repository_id == repository_id,
                FileImport.source_file_id.in_(test_file_ids),
                FileImport.target_file_id != None,
            )
        )
        test_imports = imports_res.all()
        # map (source_id, test_id)
        import_pairs = {(tgt_id, src_id) for src_id, tgt_id in test_imports}

        mappings_dict: Dict[Tuple[uuid.UUID, uuid.UUID], Tuple[str, str]] = {}

        # 1. Name convention matching
        for src_path, src_file in source_files.items():
            base_name, _ = posixpath.splitext(posixpath.basename(src_path))
            dir_name = posixpath.dirname(src_path)

            for test_path, test_file in test_files.items():
                test_base = posixpath.basename(test_path).lower()
                clean_test_base = (
                    test_base.replace("test_", "")
                    .replace("_test", "")
                    .replace(".test", "")
                    .replace(".spec", "")
                    .split(".")[0]
                )

                if clean_test_base.lower() == base_name.lower():
                    # Same directory or matching subdirectory structure
                    mappings_dict[(src_file.id, test_file.id)] = ("name_convention", "high")

        # 2. Import analysis matching
        for src_id, test_id in import_pairs:
            key = (src_id, test_id)
            if key not in mappings_dict:
                mappings_dict[key] = ("import_analysis", "high")

        # 3. Directory proximity
        for src_path, src_file in source_files.items():
            src_dir = posixpath.dirname(src_path)
            for test_path, test_file in test_files.items():
                key = (src_file.id, test_file.id)
                if key in mappings_dict:
                    continue
                test_dir = posixpath.dirname(test_path)
                if src_dir and (src_dir in test_dir or test_dir in src_dir):
                    # Proximity match
                    mappings_dict[key] = ("directory_proximity", "low")

        # Persist to database
        db_mappings: List[TestMapping] = []
        for (src_id, test_id), (method, confidence) in mappings_dict.items():
            db_mappings.append(
                TestMapping(
                    repository_id=repository_id,
                    source_file_id=src_id,
                    test_file_id=test_id,
                    method=method,
                    confidence=confidence,
                )
            )

        if db_mappings:
            db.add_all(db_mappings)
            await db.commit()

        return db_mappings

    @staticmethod
    async def get_test_intel_overview(
        db: AsyncSession,
        repository_id: uuid.UUID,
    ) -> TestIntelOverview:
        # Count test files vs source files
        counts_res = await db.execute(
            select(
                func.count().filter(RepoFile.is_test == True),
                func.count().filter(RepoFile.is_test == False),
            ).where(RepoFile.repository_id == repository_id)
        )
        test_count, source_count = counts_res.one()
        test_count = test_count or 0
        source_count = source_count or 0

        # Count distinct mapped source files
        mapped_res = await db.execute(
            select(func.count(func.distinct(TestMapping.source_file_id)))
            .where(TestMapping.repository_id == repository_id)
        )
        mapped_count = mapped_res.scalar() or 0

        coverage_pct = round((mapped_count / source_count * 100), 1) if source_count > 0 else 0.0

        # Detect frameworks
        frameworks = set()
        test_files_res = await db.execute(
            select(RepoFile.path, RepoFile.content)
            .where(RepoFile.repository_id == repository_id, RepoFile.is_test == True)
            .limit(50)
        )
        for path, content in test_files_res.all():
            lower_path = path.lower()
            lower_content = (content or "").lower()
            if "pytest" in lower_content or "conftest.py" in lower_path:
                frameworks.add("pytest")
            elif "unittest" in lower_content:
                frameworks.add("unittest")
            elif "jest" in lower_content or ".spec." in lower_path or ".test." in lower_path:
                frameworks.add("Jest / Vitest")
            elif "junit" in lower_content or "org.junit" in lower_content:
                frameworks.add("JUnit")
            elif "_test.go" in lower_path or "testing.t" in lower_content:
                frameworks.add("Go testing")

        # Load sample mappings
        sample_res = await db.execute(
            select(
                TestMapping.method,
                TestMapping.confidence,
                RepoFile.path,
            )
            .join(RepoFile, TestMapping.test_file_id == RepoFile.id)
            .where(TestMapping.repository_id == repository_id)
            .limit(10)
        )
        samples = [
            {"test_file": path, "method": method, "confidence": conf}
            for method, conf, path in sample_res.all()
        ]

        return TestIntelOverview(
            test_files_count=test_count,
            source_files_count=source_count,
            mapped_source_files_count=mapped_count,
            coverage_proxy_pct=coverage_pct,
            detected_frameworks=list(frameworks) or ["Standard test conventions"],
            sample_mappings=samples,
        )

    @staticmethod
    async def get_tests_for_file(
        db: AsyncSession,
        repository_id: uuid.UUID,
        file_path: str,
    ) -> List[ExistingTest]:
        # Find file id
        fid_res = await db.execute(
            select(RepoFile.id).where(
                RepoFile.repository_id == repository_id,
                RepoFile.path == file_path,
            )
        )
        fid = fid_res.scalar_one_or_none()
        if not fid:
            return []

        res = await db.execute(
            select(TestMapping.method, TestMapping.confidence, RepoFile.path)
            .join(RepoFile, TestMapping.test_file_id == RepoFile.id)
            .where(
                TestMapping.repository_id == repository_id,
                TestMapping.source_file_id == fid,
            )
        )
        tests = []
        for method, conf, t_path in res.all():
            tests.append(
                ExistingTest(
                    path=t_path,
                    method=method,
                    confidence=conf,
                    kind="fact",
                )
            )
        return tests

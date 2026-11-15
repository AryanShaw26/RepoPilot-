import posixpath
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import FileImport, RepoFile
from app.schemas.graph import (
    FileDependenciesResponse,
    FileDependencyItem,
    GraphEdge,
    GraphNode,
    GraphResponse,
    GraphStats,
)


def tarjan_scc_iterative(adj: Dict[str, List[str]]) -> List[List[str]]:
    """
    Iterative Tarjan SCC algorithm to detect cycles safely without recursion.
    Returns list of strongly connected components with size > 1.
    """
    index = 0
    indices: Dict[str, int] = {}
    lowlink: Dict[str, int] = {}
    on_stack: Dict[str, bool] = {}
    stack: List[str] = []
    sccs: List[List[str]] = []

    nodes = list(adj.keys())

    for root in nodes:
        if root in indices:
            continue

        call_stack = [(root, 0, iter(adj.get(root, [])))]
        indices[root] = lowlink[root] = index
        index += 1
        stack.append(root)
        on_stack[root] = True

        while call_stack:
            v, state, it = call_stack[-1]
            advanced = False

            for w in it:
                if w not in indices:
                    indices[w] = lowlink[w] = index
                    index += 1
                    stack.append(w)
                    on_stack[w] = True
                    call_stack.append((w, 0, iter(adj.get(w, []))))
                    advanced = True
                    break
                elif on_stack.get(w, False):
                    lowlink[v] = min(lowlink[v], indices[w])

            if advanced:
                continue

            if lowlink[v] == indices[v]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    scc.append(w)
                    if w == v:
                        break
                if len(scc) > 1:
                    sccs.append(scc)

            call_stack.pop()
            if call_stack:
                parent, _, _ = call_stack[-1]
                lowlink[parent] = min(lowlink[parent], lowlink[v])

    return sccs


class GraphService:
    @staticmethod
    async def build_graph(
        db: AsyncSession,
        repository_id: uuid.UUID,
        level: str = "file",
        path_prefix: Optional[str] = None,
        include_external: bool = False,
    ) -> GraphResponse:
        # Load all repo files
        files_stmt = select(RepoFile).where(RepoFile.repository_id == repository_id)
        if path_prefix:
            files_stmt = files_stmt.where(RepoFile.path.startswith(path_prefix))
        res_files = await db.execute(files_stmt)
        files = res_files.scalars().all()
        files_by_id = {f.id: f for f in files}

        # Load file imports
        imports_stmt = select(FileImport).where(FileImport.repository_id == repository_id)
        res_imports = await db.execute(imports_stmt)
        imports = res_imports.scalars().all()

        note: Optional[str] = None
        # If file count > 800, auto-switch to folder
        if len(files) > 800 and level == "file":
            level = "folder"
            note = f"Repository contains {len(files)} files. Showing folder-level dependency view for performance."

        if level == "folder":
            return GraphService._build_folder_graph(files, imports, include_external, note)
        else:
            return GraphService._build_file_graph(files, imports, include_external, note)

    @staticmethod
    def _build_file_graph(
        files: List[RepoFile],
        imports: List[FileImport],
        include_external: bool,
        note: Optional[str],
    ) -> GraphResponse:
        nodes_dict: Dict[str, GraphNode] = {}
        in_degree: Dict[str, int] = defaultdict(int)
        out_degree: Dict[str, int] = defaultdict(int)
        adj: Dict[str, List[str]] = defaultdict(list)
        edge_weights: Dict[Tuple[str, str, str], int] = defaultdict(int)
        files_by_id = {f.id: f for f in files}

        for f in files:
            nodes_dict[str(f.id)] = GraphNode(
                id=str(f.id),
                label=posixpath.basename(f.path),
                path=f.path,
                language=f.language,
                is_entry_point=f.is_entry_point,
                type="file",
            )

        internal_count = 0
        external_count = 0

        for imp in imports:
            src_id_str = str(imp.source_file_id)
            if src_id_str not in nodes_dict:
                continue

            if imp.target_file_id and str(imp.target_file_id) in nodes_dict:
                tgt_id_str = str(imp.target_file_id)
                internal_count += 1
                out_degree[src_id_str] += 1
                in_degree[tgt_id_str] += 1
                edge_key = (src_id_str, tgt_id_str, "import")
                if edge_weights[edge_key] == 0:
                    adj[src_id_str].append(tgt_id_str)
                edge_weights[edge_key] += 1
            elif imp.is_external and include_external and imp.package_name:
                external_count += 1
                pkg_id = f"pkg_{imp.package_name}"
                if pkg_id not in nodes_dict:
                    nodes_dict[pkg_id] = GraphNode(
                        id=pkg_id,
                        label=imp.package_name,
                        path=imp.package_name,
                        type="package",
                    )
                out_degree[src_id_str] += 1
                in_degree[pkg_id] += 1
                edge_weights[(src_id_str, pkg_id, "external")] += 1

        edges = [
            GraphEdge(
                id=f"e_{source}_{target}_{kind}",
                source=source,
                target=target,
                kind=kind,
                weight=weight,
            )
            for (source, target, kind), weight in edge_weights.items()
        ]

        # Detect cycles
        cycles = tarjan_scc_iterative(adj)
        nodes_in_cycles = {node_id for scc in cycles for node_id in scc}

        # Update degrees and cycle flags
        for nid, node in nodes_dict.items():
            node.in_degree = in_degree[nid]
            node.out_degree = out_degree[nid]
            if nid in nodes_in_cycles:
                node.in_cycle = True

        stats = GraphStats(
            total_nodes=len(nodes_dict),
            total_edges=len(edges),
            internal_imports=internal_count,
            external_imports=external_count,
            cycles_detected=len(cycles),
            note=note,
        )

        return GraphResponse(
            nodes=list(nodes_dict.values()),
            edges=edges,
            stats=stats,
            cycles=cycles,
        )

    @staticmethod
    def _build_folder_graph(
        files: List[RepoFile],
        imports: List[FileImport],
        include_external: bool,
        note: Optional[str],
    ) -> GraphResponse:
        nodes_dict: Dict[str, GraphNode] = {}
        file_to_folder: Dict[uuid.UUID, str] = {}
        folder_file_counts: Dict[str, int] = defaultdict(int)
        edges_map: Dict[Tuple[str, str], int] = defaultdict(int)

        for f in files:
            folder = posixpath.dirname(f.path) or "."
            file_to_folder[f.id] = folder
            folder_file_counts[folder] += 1

        for folder, count in folder_file_counts.items():
            nodes_dict[folder] = GraphNode(
                id=folder,
                label=folder,
                path=folder,
                type="folder",
                file_count=count,
            )

        internal_count = 0
        external_count = 0

        for imp in imports:
            src_folder = file_to_folder.get(imp.source_file_id)
            if not src_folder:
                continue

            if imp.target_file_id and imp.target_file_id in file_to_folder:
                tgt_folder = file_to_folder[imp.target_file_id]
                if src_folder != tgt_folder:
                    edges_map[(src_folder, tgt_folder)] += 1
                    internal_count += 1
            elif imp.is_external and include_external and imp.package_name:
                pkg_id = f"pkg_{imp.package_name}"
                if pkg_id not in nodes_dict:
                    nodes_dict[pkg_id] = GraphNode(
                        id=pkg_id,
                        label=imp.package_name,
                        path=imp.package_name,
                        type="package",
                    )
                edges_map[(src_folder, pkg_id)] += 1
                external_count += 1

        edges: List[GraphEdge] = []
        adj: Dict[str, List[str]] = defaultdict(list)
        in_degree: Dict[str, int] = defaultdict(int)
        out_degree: Dict[str, int] = defaultdict(int)

        for (src, tgt), weight in edges_map.items():
            edges.append(
                GraphEdge(
                    id=f"e_{src}_{tgt}",
                    source=src,
                    target=tgt,
                    kind="import",
                    weight=weight,
                )
            )
            adj[src].append(tgt)
            out_degree[src] += weight
            in_degree[tgt] += weight

        cycles = tarjan_scc_iterative(adj)
        nodes_in_cycles = {node_id for scc in cycles for node_id in scc}

        for nid, node in nodes_dict.items():
            node.in_degree = in_degree[nid]
            node.out_degree = out_degree[nid]
            if nid in nodes_in_cycles:
                node.in_cycle = True

        stats = GraphStats(
            total_nodes=len(nodes_dict),
            total_edges=len(edges),
            internal_imports=internal_count,
            external_imports=external_count,
            cycles_detected=len(cycles),
            note=note,
        )

        return GraphResponse(
            nodes=list(nodes_dict.values()),
            edges=edges,
            stats=stats,
            cycles=cycles,
        )

    @staticmethod
    async def get_file_dependencies(
        db: AsyncSession,
        repository_id: uuid.UUID,
        file_path: str,
    ) -> FileDependenciesResponse:
        # Find file
        f_res = await db.execute(
            select(RepoFile).where(
                RepoFile.repository_id == repository_id,
                RepoFile.path == file_path,
            )
        )
        file_obj = f_res.scalar_one_or_none()
        if not file_obj:
            return FileDependenciesResponse(path=file_path, imports=[], imported_by=[])

        # Find direct imports
        imp_res = await db.execute(
            select(FileImport, RepoFile.path)
            .outerjoin(RepoFile, FileImport.target_file_id == RepoFile.id)
            .where(
                FileImport.repository_id == repository_id,
                FileImport.source_file_id == file_obj.id,
            )
        )
        imports: List[FileDependencyItem] = []
        for imp, tgt_path in imp_res.all():
            imports.append(
                FileDependencyItem(
                    specifier=imp.raw_specifier,
                    target_path=tgt_path,
                    is_external=imp.is_external,
                    package_name=imp.package_name,
                    line=imp.line,
                )
            )

        # Find files that import this file (imported_by)
        rev_res = await db.execute(
            select(FileImport, RepoFile.path)
            .join(RepoFile, FileImport.source_file_id == RepoFile.id)
            .where(
                FileImport.repository_id == repository_id,
                FileImport.target_file_id == file_obj.id,
            )
        )
        imported_by: List[FileDependencyItem] = []
        for imp, src_path in rev_res.all():
            imported_by.append(
                FileDependencyItem(
                    specifier=imp.raw_specifier,
                    target_path=src_path,
                    is_external=False,
                    line=imp.line,
                )
            )

        return FileDependenciesResponse(path=file_path, imports=imports, imported_by=imported_by)

    @staticmethod
    async def reverse_dependencies(
        db: AsyncSession,
        repository_id: uuid.UUID,
        file_ids: List[uuid.UUID],
        depth: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Calculates reverse dependencies up to `depth` levels (facts for planner).
        Returns list of {path: str, reason: str, kind: 'fact'}
        """
        if not file_ids:
            return []

        # Load all internal import edges for this repository
        edges_res = await db.execute(
            select(FileImport.source_file_id, FileImport.target_file_id, RepoFile.path)
            .join(RepoFile, FileImport.source_file_id == RepoFile.id)
            .where(
                FileImport.repository_id == repository_id,
                FileImport.target_file_id != None,
            )
        )
        rows = edges_res.all()

        # target_id -> list of (source_id, source_path)
        rev_adj = defaultdict(list)
        for src_id, tgt_id, src_path in rows:
            rev_adj[tgt_id].append((src_id, src_path))

        visited: Set[uuid.UUID] = set(file_ids)
        current_level = set(file_ids)
        impacted: List[Dict[str, Any]] = []

        # Load paths of original files
        orig_paths_res = await db.execute(
            select(RepoFile.id, RepoFile.path).where(RepoFile.id.in_(file_ids))
        )
        paths_by_id = dict(orig_paths_res.all())

        for step in range(depth):
            next_level = set()
            for fid in current_level:
                caller_info = rev_adj.get(fid, [])
                for caller_id, caller_path in caller_info:
                    if caller_id not in visited:
                        visited.add(caller_id)
                        next_level.add(caller_id)
                        target_name = paths_by_id.get(fid, "modified file")
                        reason = f"directly imports {target_name}" if step == 0 else f"transitively depends on {target_name}"
                        impacted.append({
                            "path": caller_path,
                            "reason": reason,
                            "kind": "fact",
                        })
            current_level = next_level

        return impacted

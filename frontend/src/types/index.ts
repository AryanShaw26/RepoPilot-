export type AnalysisStage =
  | "queued"
  | "fetching"
  | "parsing"
  | "indexing"
  | "embedding"
  | "ready"
  | "failed";

export interface RepositoryStats {
  files_count: number;
  symbols_count: number;
  tests_count: number;
  languages_count: number;
}

export interface RepositoryOverview {
  id: string;
  owner: string;
  name: string;
  url: string;
  branch: string;
  commit_sha?: string | null;
  description?: string | null;
  stars?: number | null;
  license?: string | null;
  topics: string[];
  size_kb?: number | null;
  languages: Record<string, number>;
  frameworks: Array<{ name: string; evidence: string }>;
  entry_points: Array<{ path: string; reason: string }>;
  readme_excerpt?: string | null;
  architecture_summary?: string | null;
  status: "pending" | "processing" | "ready" | "failed";
  created_at: string;
  updated_at: string;
  stats?: RepositoryStats | null;
}

export interface RepositorySummary {
  id: string;
  owner: string;
  name: string;
  url: string;
  branch: string;
  commit_sha?: string | null;
  description?: string | null;
  stars?: number | null;
  status: "pending" | "processing" | "ready" | "failed";
  created_at: string;
}

export interface AnalysisJob {
  id: string;
  repository_id: string;
  stage: AnalysisStage;
  progress: number;
  message?: string | null;
  error?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  created_at: string;
}

export interface TreeNode {
  name: string;
  path: string;
  type: "file" | "directory";
  size?: number | null;
  language?: string | null;
  is_test?: boolean | null;
  is_entry_point?: boolean | null;
}

export interface FileContent {
  path: string;
  directory: string;
  language?: string | null;
  size_bytes: number;
  line_count?: number | null;
  is_test: boolean;
  is_entry_point: boolean;
  content?: string | null;
}

export interface SymbolItem {
  id: string;
  name: string;
  qualified_name?: string | null;
  kind: string;
  start_line: number;
  end_line: number;
  signature?: string | null;
  docstring?: string | null;
  file_path?: string | null;
}

export interface SearchResultItem {
  file_path: string;
  start_line: number;
  end_line: number;
  snippet: string;
  score: number;
  source: string[];
  symbol_name?: string | null;
  kind?: string | null;
}

export interface SearchResponse {
  results: SearchResultItem[];
  semantic_available: boolean;
}

export interface GraphNode {
  id: string;
  label: string;
  path: string;
  language?: string | null;
  in_degree: number;
  out_degree: number;
  type: "file" | "folder" | "package";
  is_entry_point?: boolean;
  in_cycle?: boolean;
  file_count?: number | null;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  kind: string;
  weight: number;
}

export interface GraphStats {
  total_nodes: number;
  total_edges: number;
  internal_imports: number;
  external_imports: number;
  cycles_detected: number;
  note?: string | null;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: GraphStats;
  cycles: string[][];
}

export interface FileDependencyItem {
  specifier: string;
  target_path?: string | null;
  is_external: boolean;
  package_name?: string | null;
  line?: number | null;
}

export interface FileDependenciesResponse {
  path: string;
  imports: FileDependencyItem[];
  imported_by: FileDependencyItem[];
}

export interface EvidenceSnippet {
  start_line: number;
  end_line: number;
  snippet: string;
}

export interface RankedResult {
  rank: number;
  file_path: string;
  symbol?: {
    name: string;
    kind: string;
    start_line: number;
    end_line: number;
  } | null;
  score: number;
  retrieval_sources: string[];
  why_relevant: { text: string; kind: "hypothesis" };
  evidence: EvidenceSnippet[];
}

export interface Hypothesis {
  id: string;
  text: string;
  kind: "hypothesis";
  confidence: "low" | "medium" | "high";
  evidence_refs: string[];
  unsupported?: boolean;
}

export interface InvestigationResponse {
  id: string;
  status: "pending" | "processing" | "ready" | "failed";
  issue: {
    title?: string | null;
    body: string;
    url?: string | null;
  };
  extracted_terms: {
    identifiers?: string[];
    error_strings?: string[];
    file_hints?: string[];
    keywords?: string[];
  };
  evidence_strength: "weak" | "moderate" | "strong";
  results: RankedResult[];
  hypotheses: Hypothesis[];
  disclaimer: string;
  error?: string | null;
  created_at: string;
}

export interface PlanStep {
  order: number;
  title: string;
  description: string;
  files: string[];
  kind: "fact" | "hypothesis";
}

export interface ImpactedFile {
  path: string;
  reason: string;
  kind: "fact";
}

export interface RiskItem {
  text: string;
  kind: "hypothesis";
  confidence: "low" | "medium" | "high";
}

export interface ExistingTest {
  path: string;
  method: string;
  confidence: string;
  kind: "fact";
}

export interface RecommendedTest {
  scenario: string;
  kind: "hypothesis";
}

export interface PlanContent {
  summary: { text: string; kind: "hypothesis" };
  steps: PlanStep[];
  impacted_files: ImpactedFile[];
  risks: RiskItem[];
  validation_checklist: string[];
  tests: {
    existing: ExistingTest[];
    recommended: RecommendedTest[];
  };
  disclaimer: string;
}

export interface PlanResponse {
  id: string;
  investigation_id: string;
  user_notes?: string | null;
  plan: PlanContent;
  markdown?: string | null;
  created_at: string;
  disclaimer: string;
}

export interface TestIntelOverview {
  test_files_count: number;
  source_files_count: number;
  mapped_source_files_count: number;
  coverage_proxy_pct: number;
  detected_frameworks: string[];
  sample_mappings: Array<{
    test_file: string;
    method: string;
    confidence: string;
  }>;
  disclaimer: string;
}

export interface Capabilities {
  semantic_search: boolean;
  llm_available: boolean;
  llm_provider: string;
  embedding_provider: string;
  max_repo_size_mb: number;
  max_files: number;
  max_file_bytes: number;
}

export interface HealthStatus {
  status: "ok" | "degraded";
  db: boolean;
  migrated: boolean;
  semantic_enabled: boolean;
  llm_configured: boolean;
  github_token_configured: boolean;
  version: string;
}

export interface TestRecommendations {
  existing: ExistingTest[];
  recommended: RecommendedTest[];
}

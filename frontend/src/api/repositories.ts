import { apiClient } from "./client";
import {
  AnalysisJob,
  FileContent,
  RepositoryOverview,
  RepositorySummary,
  SearchResultItem,
  SymbolItem,
  TreeNode,
} from "../types";

export const getRepositories = async (): Promise<RepositorySummary[]> => {
  const resp = await apiClient.get<RepositorySummary[]>("/repositories");
  return resp.data;
};

export const getRepositoryOverview = async (repoId: string): Promise<RepositoryOverview> => {
  const resp = await apiClient.get<RepositoryOverview>(`/repositories/${repoId}`);
  return resp.data;
};

export const analyzeRepository = async (
  url: string,
  branch?: string
): Promise<{ repository_id: string; job_id: string; status: string }> => {
  const resp = await apiClient.post("/repositories", { url, branch });
  return resp.data;
};

export const reanalyseRepository = async (
  repoId: string
): Promise<{ repository_id: string; job_id: string; status: string }> => {
  const resp = await apiClient.post(`/repositories/${repoId}/reanalyse`);
  return resp.data;
};

export const deleteRepository = async (repoId: string): Promise<void> => {
  await apiClient.delete(`/repositories/${repoId}`);
};

export const getLatestJob = async (repoId: string): Promise<AnalysisJob> => {
  const resp = await apiClient.get<AnalysisJob>(`/repositories/${repoId}/job`);
  return resp.data;
};

export const getTree = async (repoId: string, path: string = ""): Promise<TreeNode[]> => {
  const resp = await apiClient.get<TreeNode[]>(`/repositories/${repoId}/tree`, {
    params: { path },
  });
  return resp.data;
};

export const getFileContent = async (repoId: string, path: string): Promise<FileContent> => {
  const resp = await apiClient.get<FileContent>(`/repositories/${repoId}/files`, {
    params: { path },
  });
  return resp.data;
};

export const getFileSymbols = async (repoId: string, path: string): Promise<SymbolItem[]> => {
  const resp = await apiClient.get<SymbolItem[]>(`/repositories/${repoId}/files/symbols`, {
    params: { path },
  });
  return resp.data;
};

export const getSymbolSearch = async (
  repoId: string,
  query: string,
  kind?: string
): Promise<SearchResultItem[]> => {
  const resp = await apiClient.get<SearchResultItem[]>(`/repositories/${repoId}/symbols`, {
    params: { q: query, kind },
  });
  return resp.data;
};

export const explainSymbol = async (
  repoId: string,
  symbolId: string
): Promise<{ explanation: string; kind: string; confidence: string }> => {
  const resp = await apiClient.post(`/repositories/${repoId}/symbols/${symbolId}/explain`);
  return resp.data;
};

export const getTestsForFile = async (
  repoId: string,
  path: string
): Promise<Array<{ path: string; method: string; confidence: string; kind: "fact" }>> => {
  const resp = await apiClient.get<Array<{ path: string; method: string; confidence: string; kind: "fact" }>>(`/repositories/${repoId}/tests/for`, {
    params: { path },
  });
  return resp.data;
};


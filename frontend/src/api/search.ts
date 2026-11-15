import { apiClient } from "./client";
import { SearchResponse } from "../types";

export interface SearchFilters {
  language?: string;
  path_prefix?: string;
  exclude_tests?: boolean;
}

export const searchRepository = async (
  repoId: string,
  query: string,
  mode: "keyword" | "symbol" | "semantic" | "hybrid" = "hybrid",
  limit: number = 20,
  filters?: SearchFilters
): Promise<SearchResponse> => {
  const resp = await apiClient.post<SearchResponse>(`/repositories/${repoId}/search`, {
    query,
    mode,
    limit,
    filters,
  });
  return resp.data;
};

import { apiClient } from "./client";
import { FileDependenciesResponse, GraphResponse } from "../types";

export const getDependencyGraph = async (
  repoId: string,
  level: "file" | "folder" = "file",
  pathPrefix?: string,
  includeExternal: boolean = false
): Promise<GraphResponse> => {
  const resp = await apiClient.get<GraphResponse>(`/repositories/${repoId}/graph`, {
    params: {
      level,
      path_prefix: pathPrefix,
      include_external: includeExternal,
    },
  });
  return resp.data;
};

export const getFileDependencies = async (
  repoId: string,
  path: string
): Promise<FileDependenciesResponse> => {
  const resp = await apiClient.get<FileDependenciesResponse>(
    `/repositories/${repoId}/files/dependencies`,
    {
      params: { path },
    }
  );
  return resp.data;
};

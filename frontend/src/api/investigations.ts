import { apiClient } from "./client";
import { InvestigationResponse, TestRecommendations } from "../types";

export interface CreateInvestigationParams {
  source_type: "text" | "github_issue";
  issue_title?: string;
  issue_body?: string;
  issue_url?: string;
}

export const createInvestigation = async (
  repoId: string,
  params: CreateInvestigationParams
): Promise<{ investigation_id: string; status: string }> => {
  const resp = await apiClient.post(`/repositories/${repoId}/investigations`, params);
  return resp.data;
};

export const getInvestigation = async (invId: string): Promise<InvestigationResponse> => {
  const resp = await apiClient.get<InvestigationResponse>(`/investigations/${invId}`);
  return resp.data;
};

export const listInvestigations = async (
  repoId: string
): Promise<Array<{ id: string; title: string; status: string; created_at: string }>> => {
  const resp = await apiClient.get<Array<{ id: string; title: string; status: string; created_at: string }>>(`/repositories/${repoId}/investigations`);
  return resp.data;
};

export const getTestRecommendations = async (
  investigationId: string
): Promise<TestRecommendations> => {
  const resp = await apiClient.post<TestRecommendations>(
    `/investigations/${investigationId}/test-recommendations`
  );
  return resp.data;
};

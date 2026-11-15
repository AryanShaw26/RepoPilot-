import { apiClient } from "./client";
import { PlanResponse, TestIntelOverview } from "../types";

export const createPlan = async (
  invId: string,
  userNotes?: string
): Promise<PlanResponse> => {
  const resp = await apiClient.post<PlanResponse>(`/investigations/${invId}/plan`, {
    user_notes: userNotes,
  });
  return resp.data;
};

export const getPlan = async (planId: string): Promise<PlanResponse> => {
  const resp = await apiClient.get<PlanResponse>(`/plans/${planId}`);
  return resp.data;
};

export const getTestIntelOverview = async (repoId: string): Promise<TestIntelOverview> => {
  const resp = await apiClient.get<TestIntelOverview>(`/repositories/${repoId}/tests`);
  return resp.data;
};

export const exportPlanMarkdown = async (planId: string): Promise<string> => {
  const resp = await apiClient.get<string>(`/plans/${planId}/export`, {
    params: { format: "markdown" },
    responseType: "text",
  });
  return resp.data;
};

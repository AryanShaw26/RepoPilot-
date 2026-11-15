import { apiClient } from "./client";
import type { Capabilities, HealthStatus } from "../types";

export async function getHealth(): Promise<HealthStatus> {
  const response = await apiClient.get<HealthStatus>("/health");
  return response.data;
}

export async function getCapabilities(): Promise<Capabilities> {
  const response = await apiClient.get<Capabilities>("/meta/capabilities");
  return response.data;
}

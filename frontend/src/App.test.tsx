import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { App } from "./App";
import { getCapabilities, getHealth } from "./api/health";
import { getRepositories } from "./api/repositories";
import type { Capabilities, HealthStatus } from "./types";

vi.mock("./api/health", () => ({
  getCapabilities: vi.fn(),
  getHealth: vi.fn(),
}));

vi.mock("./api/repositories", () => ({
  getRepositories: vi.fn(),
}));

const healthyStatus: HealthStatus = {
  status: "ok",
  db: true,
  migrated: true,
  semantic_enabled: false,
  llm_configured: false,
  github_token_configured: false,
  version: "test",
};

const capabilities: Capabilities = {
  semantic_search: false,
  llm_available: false,
  llm_provider: "none",
  embedding_provider: "none",
  max_repo_size_mb: 100,
  max_files: 5000,
  max_file_bytes: 1_000_000,
};

function configureMocks(health: HealthStatus) {
  vi.mocked(getHealth).mockResolvedValue(health);
  vi.mocked(getCapabilities).mockResolvedValue(capabilities);
  vi.mocked(getRepositories).mockResolvedValue([]);
}

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.resetAllMocks();
});

describe("application readiness banner", () => {
  it("explains when the database is not ready", async () => {
    configureMocks({ ...healthyStatus, status: "degraded", migrated: false });

    render(<App />);

    expect(await screen.findByText(/Backend is running but the database isn’t ready/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Analyze repository/ }).hasAttribute("disabled")).toBe(true);
  });

  it("allows analysis when the backend and database are ready", async () => {
    configureMocks(healthyStatus);

    render(<App />);

    const analyzeButton = await screen.findByRole("button", { name: /Analyze repository/ });
    await waitFor(() => expect(analyzeButton.hasAttribute("disabled")).toBe(false));
    expect(screen.queryByText(/database isn’t ready/)).toBeNull();
  });
});

import { describe, expect, it } from "vitest";
import { ApiError } from "../api/client";
import { presentApiError } from "./apiErrors";

describe("presentApiError", () => {
  it("explains invalid repository URLs", () => {
    const result = presentApiError(
      new ApiError({ code: "INVALID_URL", message: "Invalid repository URL." })
    );

    expect(result.code).toBe("INVALID_URL");
    expect(result.title).toBe("Repository URL is invalid");
    expect(result.message).toContain("valid public GitHub repository URL");
  });

  it("preserves backend guidance for invalid arguments", () => {
    const result = presentApiError(
      new ApiError({ code: "INVALID_ARGUMENT", message: "Issue URL must belong to this repository." })
    );

    expect(result.code).toBe("INVALID_ARGUMENT");
    expect(result.title).toBe("Some information needs attention");
    expect(result.message).toBe("Issue URL must belong to this repository.");
  });
});

import { ApiError } from "../api/client";

export interface ErrorPresentation {
  title: string;
  message: string;
  code?: string;
}

export function presentApiError(error: unknown): ErrorPresentation {
  if (error instanceof ApiError) {
    if (error.code === "INVALID_URL") {
      return {
        title: "Repository URL is invalid",
        message: "Enter a valid public GitHub repository URL.",
        code: error.code,
      };
    }
    if (error.code === "INVALID_ARGUMENT") {
      return {
        title: "Some information needs attention",
        message: error.message || "Review the repository URL, issue URL, and other supplied values.",
        code: error.code,
      };
    }
    if (error.code === "DATABASE_UNAVAILABLE") {
      return {
        title: "Database unavailable",
        message: "The backend database is unavailable. Try again after the service is restored.",
        code: error.code,
      };
    }
    return {
      title: "Request failed",
      message: error.message,
      code: error.code,
    };
  }
  return {
    title: "Request failed",
    message: error instanceof Error ? error.message : "An unexpected error occurred.",
  };
}

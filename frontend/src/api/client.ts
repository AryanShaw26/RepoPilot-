import axios, { AxiosError } from "axios";

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL;
if (!configuredBaseUrl) {
  console.warn(
    "VITE_API_BASE_URL is not set; defaulting to http://localhost:8000/api/v1."
  );
}
const BASE_URL = configuredBaseUrl || "http://localhost:8000/api/v1";

export interface ApiErrorDetail {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export class ApiError extends Error {
  code: string;
  details: Record<string, unknown>;

  constructor(error: ApiErrorDetail) {
    super(error.message);
    this.name = "ApiError";
    this.code = error.code;
    this.details = error.details || {};
  }
}

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Attach Session ID
apiClient.interceptors.request.use((config) => {
  const sessionId = globalThis.localStorage?.getItem("rp-session-id");
  if (sessionId) {
    config.headers["X-Session-Id"] = sessionId;
  }
  return config;
});

// Capture Session ID & Handle standard error envelope
apiClient.interceptors.response.use(
  (response) => {
    const newSessionId = response.headers["x-session-id"];
    if (newSessionId) {
      globalThis.localStorage?.setItem("rp-session-id", newSessionId);
    }
    return response;
  },
  (error: AxiosError<{ error?: ApiErrorDetail }>) => {
    const apiError = error.response?.data?.error;
    if (apiError && typeof apiError.code === "string" && typeof apiError.message === "string") {
      throw new ApiError(apiError);
    }
    throw new ApiError({
      code: "NETWORK_ERROR",
      message: error.message || "Network communication failed.",
      details: {},
    });
  }
);

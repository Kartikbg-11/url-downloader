/**
 * API client for the URL Application Downloader backend.
 *
 * All API calls go through this centralized module to ensure
 * consistent error handling and URL configuration.
 */

import type {
  Download,
  CreateDownloadRequest,
  DownloadsListResponse,
  HealthResponse,
  ApiError,
  MediaInfo,
} from "@/types/download";
import { getApiBaseUrl, BACKEND_PORT } from "./config";

const API_BASE = getApiBaseUrl();

/**
 * Build URL with optional query parameters
 */
function buildUrl(path: string, params?: Record<string, string | number>): string {
  const url = `${API_BASE}${path}`;
  
  // Parse existing query parameters from path
  const urlObj = new URL(url, 'http://localhost');
  
  // Add additional parameters
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        urlObj.searchParams.set(key, String(value));
      }
    });
  }
  
  // Return just pathname + search (relative URL)
  return `${urlObj.pathname}${urlObj.search}`;
}

/**
 * Handle API errors consistently
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorData: ApiError;

    try {
      const body = await response.json();
      // FastAPI wraps errors raised by HTTPException in `detail`.
      errorData = body.detail?.error ? body.detail : body;
    } catch {
      errorData = {
        error: {
          code: "REQUEST_FAILED",
          message: `Request failed with status ${response.status}`,
        },
      };
    }

    throw new ApiClientError(
      errorData.error?.message || "Request failed",
      errorData.error?.code || "REQUEST_FAILED",
      response.status,
      errorData
    );
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

/**
 * Custom error class for API errors
 */
export class ApiClientError extends Error {
  constructor(
    message: string,
    public code: string,
    public status: number,
    public data?: ApiError
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

/**
 * API client object with methods for each endpoint
 */
export const apiClient = {
  async getMediaInfo(url: string): Promise<MediaInfo> {
    const response = await fetch(buildUrl(`/api/downloads/media-info?XTransformPort=${BACKEND_PORT}`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    return handleResponse<MediaInfo>(response);
  },

  /**
   * Check service health
   */
  async health(): Promise<HealthResponse> {
    const response = await fetch(buildUrl(`/api/health?XTransformPort=${BACKEND_PORT}`));
    return handleResponse<HealthResponse>(response);
  },

  /**
   * Create a new download
   */
  async createDownload(request: CreateDownloadRequest): Promise<Download> {
    const response = await fetch(buildUrl(`/api/downloads?XTransformPort=${BACKEND_PORT}`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    return handleResponse<Download>(response);
  },

  /**
   * Get a single download by ID
   */
  async getDownload(downloadId: string): Promise<Download> {
    const response = await fetch(
      buildUrl(`/api/downloads/${downloadId}?XTransformPort=${BACKEND_PORT}`)
    );
    return handleResponse<Download>(response);
  },

  /**
   * List all downloads with optional filtering
   */
  async listDownloads(params?: {
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<DownloadsListResponse> {
    const response = await fetch(
      buildUrl(`/api/downloads?XTransformPort=${BACKEND_PORT}`, params)
    );
    return handleResponse<DownloadsListResponse>(response);
  },

  /**
   * Cancel an active download
   */
  async cancelDownload(downloadId: string): Promise<Download> {
    const response = await fetch(
      buildUrl(`/api/downloads/${downloadId}/cancel?XTransformPort=${BACKEND_PORT}`),
      { method: "POST" }
    );
    return handleResponse<Download>(response);
  },

  /**
   * Delete a download record and file
   */
  async deleteDownload(downloadId: string): Promise<void> {
    const response = await fetch(
      buildUrl(`/api/downloads/${downloadId}?XTransformPort=${BACKEND_PORT}`),
      { method: "DELETE" }
    );
    return handleResponse<void>(response);
  },

  /**
   * Get the downloadable file blob
   */
  async getFile(downloadId: string, filename: string): Promise<Blob> {
    const response = await fetch(
      buildUrl(`/api/downloads/${downloadId}/file?XTransformPort=${BACKEND_PORT}`)
    );

    if (!response.ok) {
      throw new ApiClientError(
        "Failed to download file",
        "FILE_DOWNLOAD_ERROR",
        response.status
      );
    }

    return response.blob();
  },

  /**
   * Return the file endpoint for a native browser download.
   *
   * Using an ordinary link avoids first buffering large media files in
   * JavaScript and keeps the click as a browser-initiated download.
   */
  getFileUrl(downloadId: string): string {
    return buildUrl(`/api/downloads/${downloadId}/file?XTransformPort=${BACKEND_PORT}`);
  },

  /**
   * Get SSE event source URL for a download
   */
  getEventSourceUrl(downloadId: string): string {
    return buildUrl(`/api/downloads/${downloadId}/events?XTransformPort=${BACKEND_PORT}`);
  },
};

export default apiClient;

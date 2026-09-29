/**
 * Download type definitions for the URL Application Downloader frontend.
 */

/** All possible download statuses */
export type DownloadStatus =
  | "queued"
  | "validating"
  | "downloading"
  | "completed"
  | "failed"
  | "cancelled";

/** Download record as returned by the API */
export interface Download {
  id: string;
  url: string;
  filename: string;
  status: DownloadStatus;
  downloaded_bytes: number;
  total_bytes: number | null;
  progress_percentage: number;
  speed_bytes_per_second: number;
  estimated_seconds_remaining: number | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

/** Progress event from SSE stream */
export interface ProgressEvent {
  id: string;
  type?: "progress" | "heartbeat";
  status: DownloadStatus;
  downloaded_bytes: number;
  total_bytes: number | null;
  progress_percentage: number;
  speed_bytes_per_second: number;
  estimated_seconds_remaining: number | null;
  terminal?: boolean;
  error?: string;
}

/** API error response */
export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: unknown[];
  };
}

/** Create download request */
export interface CreateDownloadRequest {
  url: string;
  format_id?: string;
  media_type?: "video" | "audio";
}

export interface MediaFormat {
  format_id: string;
  media_type: "video" | "audio";
  label: string;
  extension: string;
  filesize: number | null;
}

export interface MediaInfo {
  title: string;
  thumbnail: string | null;
  duration: number | null;
  formats: MediaFormat[];
}

/** List downloads response */
export interface DownloadsListResponse {
  downloads: Download[];
  total: number;
}

/** Health check response */
export interface HealthResponse {
  status: string;
}

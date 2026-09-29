/**
 * Central configuration for the URL Application Downloader frontend.
 */

/**
 * Get the base URL for API requests.
 * Uses environment variable or falls back to default.
 */
export const getApiBaseUrl = (): string => {
  // For development, use the mini-service port
  return "";
};

/**
 * Backend port for the download service
 */
export const BACKEND_PORT = 8001;

/**
 * SSE reconnect delay in milliseconds
 */
export const SSE_RECONNECT_DELAY = 3000;

/**
 * Maximum SSE reconnection attempts before falling back to polling
 */
export const MAX_SSE_RECONNECT_ATTEMPTS = 3;

/**
 * Polling interval in milliseconds (fallback when SSE fails)
 */
export const POLLING_INTERVAL = 2000;

/**
 * Maximum file size display threshold (in bytes)
 */
export const MAX_DISPLAY_FILE_SIZE = 1073741824; // 1 GB

/**
 * Supported file extensions (for display purposes)
 */
export const SUPPORTED_EXTENSIONS = [
  ".apk", ".exe", ".msi", ".zip", ".rar", ".7z",
  ".dmg", ".pkg", ".deb", ".rpm", ".tar", ".gz",
  ".pdf", ".docx", ".xlsx",
];

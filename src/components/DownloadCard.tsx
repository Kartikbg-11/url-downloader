/**
 * Download Card component.
 *
 * Displays complete information about a single download including
 * progress, status, speed, and action buttons.
 */

"use client";

import { useState, useCallback } from "react";
import {
  X,
  Save,
  RotateCcw,
  Globe,
  Clock,
  AlertTriangle,
  ExternalLink,
} from "lucide-react";
import type { Download, DownloadStatus } from "@/types/download";
import { StatusBadge } from "./StatusBadge";
import { ProgressBar } from "./ProgressBar";
import {
  formatFileSize,
  formatSpeed,
  formatTimeRemaining,
  formatDate,
  truncateText,
} from "@/lib/formatters";
import { apiClient } from "@/lib/api";
import { useDownloadEvents } from "@/hooks/useDownloadEvents";
import { cn } from "@/lib/utils";

interface DownloadCardProps {
  /** Initial download data */
  download: Download;
  /** Callback when download is removed from list */
  onRemove?: (downloadId: string) => void;
  /** Callback when retry is requested */
  onRetry?: (url: string) => void;
}

/**
 * Determine progress bar variant based on status
 */
function getProgressVariant(status: DownloadStatus): "default" | "success" | "error" | "warning" {
  switch (status) {
    case "completed":
      return "success";
    case "failed":
      return "error";
    case "cancelled":
      return "warning";
    default:
      return "default";
  }
}

export function DownloadCard({ download: initialDownload, onRemove, onRetry }: DownloadCardProps) {
  const [isRemoving, setIsRemoving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // Subscribe to real-time events for this download
  const { data, isConnected } = useDownloadEvents({
    downloadId: initialDownload.id,
    initialData: initialDownload,
    onError: (err) => console.error("Download event error:", err),
  });

  // Use live data if available, otherwise initial data
  const download = data || initialDownload;
  const isActive = ["queued", "validating", "downloading"].includes(download.status);

  /**
   * Handle cancel action
   */
  const handleCancel = useCallback(async () => {
    setActionError(null);
    try {
      await apiClient.cancelDownload(download.id);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to cancel download");
    }
  }, [download.id]);

  /**
   * Handle remove/delete action
   */
  const handleRemove = useCallback(async () => {
    setActionError(null);
    setIsRemoving(true);
    try {
      await apiClient.deleteDownload(download.id);
      onRemove?.(download.id);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to remove download");
      setIsRemoving(false);
    }
  }, [download.id, onRemove]);

  /**
   * Handle retry action
   */
  const handleRetry = useCallback(() => {
    onRetry?.(download.url);
  }, [download.url, onRetry]);

  /**
   * Extract hostname from URL for display
   */
  const getDisplayHostname = (): string => {
    try {
      return new URL(download.url).hostname;
    } catch {
      return "";
    }
  };

  return (
    <div
      className={cn(
        "rounded-lg border bg-white p-4 transition-all",
        isActive && "border-blue-200 ring-1 ring-blue-100",
        download.status === "completed" && "border-green-200",
        download.status === "failed" && "border-red-200",
        download.status === "cancelled" && "border-yellow-200"
      )}
      role="article"
      aria-label={`Download: ${download.filename}`}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-gray-900 truncate" title={download.filename}>
            {truncateText(download.filename, 40)}
          </h3>
          <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
            <Globe className="h-3 w-3 flex-shrink-0" />
            <span className="truncate">{getDisplayHostname()}</span>
            <span className="text-gray-300">•</span>
            <Clock className="h-3 w-3 flex-shrink-0" />
            <span>{formatDate(download.created_at)}</span>
            {isConnected && (
              <>
                <span className="text-gray-300">•</span>
                <span className="text-green-600">Live</span>
              </>
            )}
          </div>
        </div>

        <StatusBadge status={download.status} />
      </div>

      {/* Progress section */}
      {(isActive || download.status === "completed") && (
        <div className="space-y-2 mb-3">
          <ProgressBar
            progress={download.progress_percentage}
            variant={getProgressVariant(download.status)}
          />

          {/* Stats row */}
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-600">
            <span>
              {formatFileSize(download.downloaded_bytes)}
              {download.total_bytes && ` / ${formatFileSize(download.total_bytes)}`}
            </span>

            {isActive && download.speed_bytes_per_second > 0 && (
              <span>{formatSpeed(download.speed_bytes_per_second)}</span>
            )}

            {isActive && download.estimated_seconds_remaining !== null && (
              <span>ETA: {formatTimeRemaining(download.estimated_seconds_remaining)}</span>
            )}
          </div>
        </div>
      )}

      {/* Error message */}
      {download.error && (
        <div className="flex items-start gap-2 mb-3 p-2 rounded bg-red-50 text-sm text-red-700">
          <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
          <span>{download.error}</span>
        </div>
      )}

      {/* Action error */}
      {actionError && (
        <div className="mb-3 p-2 rounded bg-red-50 text-sm text-red-700">
          {actionError}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex items-center gap-2 pt-2 border-t border-gray-100">
        {/* Cancel button - show while active */}
        {isActive && (
          <button
            onClick={handleCancel}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50 rounded-md transition-colors"
            aria-label={`Cancel download of ${download.filename}`}
          >
            <X className="h-3.5 w-3.5" />
            Cancel
          </button>
        )}

        {/* Save button - show when completed */}
        {download.status === "completed" && (
          <a
            href={apiClient.getFileUrl(download.id)}
            download={download.filename}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-green-700 hover:bg-green-50 rounded-md transition-colors"
            aria-label={`Save ${download.filename}`}
          >
            <Save className="h-3.5 w-3.5" />
            Save File
          </a>
        )}

        {/* Retry button - show when failed */}
        {download.status === "failed" && (
          <button
            onClick={handleRetry}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-blue-700 hover:bg-blue-50 rounded-md transition-colors"
            aria-label={`Retry download of ${download.filename}`}
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Retry
          </button>
        )}

        {/* Remove button - show for terminal states */}
        {!isActive && (
          <button
            onClick={handleRemove}
            disabled={isRemoving}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded-md transition-colors ml-auto disabled:opacity-50"
            aria-label={`Remove ${download.filename}`}
          >
            <X className="h-3.5 w-3.5" />
            {isRemoving ? "Removing..." : "Remove"}
          </button>
        )}
      </div>
    </div>
  );
}

export default DownloadCard;

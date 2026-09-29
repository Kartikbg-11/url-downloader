/**
 * Download History component.
 *
 * Displays list of past and current downloads with empty state.
 */

"use client";

import type { Download } from "@/types/download";
import { DownloadCard } from "./DownloadCard";
import { Inbox, AlertCircle } from "lucide-react";

interface DownloadHistoryProps {
  downloads: Download[];
  onRemove?: (downloadId: string) => void;
  onRetry?: (url: string) => void;
  isLoading?: boolean;
}

export function DownloadHistory({
  downloads,
  onRemove,
  onRetry,
  isLoading = false,
}: DownloadHistoryProps) {
  // Empty state
  if (!isLoading && downloads.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
        <div className="rounded-full bg-gray-100 p-4 mb-4">
          <Inbox className="h-8 w-8 text-gray-400" />
        </div>
        <h3 className="text-lg font-medium text-gray-900 mb-1">No downloads yet</h3>
        <p className="text-sm text-gray-500 max-w-sm">
          Paste a public media URL above, choose video or audio, and select
          the format you want. Progress will appear here in real time.
        </p>
      </div>
    );
  }

  return (
    <section aria-label="Download history">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-gray-900">
          Downloads{" "}
          <span className="text-sm font-normal text-gray-500">({downloads.length})</span>
        </h2>
      </div>

      {/* Loading skeleton */}
      {isLoading && (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="animate-pulse rounded-lg border p-4">
              <div className="flex justify-between mb-3">
                <div className="h-4 bg-gray-200 rounded w-1/3" />
                <div className="h-5 bg-gray-200 rounded-full w-20" />
              </div>
              <div className="h-2 bg-gray-100 rounded-full" />
            </div>
          ))}
        </div>
      )}

      {/* Download cards */}
      {!isLoading && (
        <div className="space-y-3">
          {downloads.map((download) => (
            <DownloadCard
              key={download.id}
              download={download}
              onRemove={onRemove}
              onRetry={onRetry}
            />
          ))}
        </div>
      )}
    </section>
  );
}

export default DownloadHistory;

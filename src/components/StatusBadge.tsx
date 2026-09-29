/**
 * Status Badge component.
 *
 * Displays a color-coded badge for download status.
 */

"use client";

import type { DownloadStatus } from "@/types/download";
import { cn } from "@/lib/utils";

interface StatusBadgeProps {
  status: DownloadStatus;
  className?: string;
  size?: "sm" | "md";
}

const statusConfig: Record<
  DownloadStatus,
  { label: string; className: string; dotClassName: string }
> = {
  queued: {
    label: "Queued",
    className: "bg-gray-100 text-gray-700 border-gray-200",
    dotClassName: "bg-gray-400",
  },
  validating: {
    label: "Validating",
    className: "bg-blue-50 text-blue-700 border-blue-200",
    dotClassName: "bg-blue-500 animate-pulse",
  },
  downloading: {
    label: "Downloading",
    className: "bg-blue-50 text-blue-700 border-blue-200",
    dotClassName: "bg-blue-500 animate-pulse",
  },
  completed: {
    label: "Completed",
    className: "bg-green-50 text-green-700 border-green-200",
    dotClassName: "bg-green-500",
  },
  failed: {
    label: "Failed",
    className: "bg-red-50 text-red-700 border-red-200",
    dotClassName: "bg-red-500",
  },
  cancelled: {
    label: "Cancelled",
    className: "bg-yellow-50 text-yellow-700 border-yellow-200",
    dotClassName: "bg-yellow-500",
  },
};

export function StatusBadge({ status, className, size = "sm" }: StatusBadgeProps) {
  const config = statusConfig[status];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-medium",
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm",
        config.className,
        className
      )}
      role="status"
      aria-label={`Status: ${config.label}`}
    >
      <span
        className={cn(
          "rounded-full",
          size === "sm" ? "h-1.5 w-1.5" : "h-2 w-2",
          config.dotClassName
        )}
        aria-hidden="true"
      />
      {config.label}
    </span>
  );
}

export default StatusBadge;

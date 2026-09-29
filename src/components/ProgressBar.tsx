/**
 * Progress Bar component.
 *
 * Displays visual progress indicator with percentage label.
 */

"use client";

import { cn } from "@/lib/utils";

interface ProgressBarProps {
  /** Progress value between 0 and 100 */
  progress: number;
  /** Optional size variant */
  size?: "sm" | "md" | "lg";
  /** Whether to show percentage label */
  showLabel?: boolean;
  /** Optional custom class name */
  className?: string;
  /** Color variant */
  variant?: "default" | "success" | "error" | "warning";
}

const variantStyles = {
  default: "bg-blue-500",
  success: "bg-green-500",
  error: "bg-red-500",
  warning: "bg-yellow-500",
};

const sizeStyles = {
  sm: "h-1.5",
  md: "h-2.5",
  lg: "h-4",
};

export function ProgressBar({
  progress,
  size = "md",
  showLabel = true,
  className,
  variant = "default",
}: ProgressBarProps) {
  // Clamp progress to valid range
  const clampedProgress = Math.min(100, Math.max(0, progress));

  return (
    <div className={cn("w-full", className)}>
      {/* Progress bar container */}
      <div
        className={cn(
          "w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800",
          sizeStyles[size]
        )}
        role="progressbar"
        aria-valuenow={clampedProgress}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${clampedProgress.toFixed(1)}% complete`}
      >
        {/* Progress fill */}
        <div
          className={cn(
            "h-full rounded-full transition-all duration-300 ease-out",
            variantStyles[variant]
          )}
          style={{ width: `${clampedProgress}%` }}
        />
      </div>

      {/* Percentage label */}
      {showLabel && (
        <div className="mt-1 flex justify-between items-center">
          <span className="text-xs text-gray-500">{clampedProgress.toFixed(1)}%</span>
        </div>
      )}
    </div>
  );
}

export default ProgressBar;

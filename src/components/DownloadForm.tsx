/**
 * Download Form component.
 *
 * Provides URL input, validation, and submission for new downloads.
 */

"use client";

import { useState, useCallback } from "react";
import { Clipboard, Download, Loader2, AlertCircle } from "lucide-react";
import { validateDownloadUrl } from "@/lib/validation";
import { apiClient, ApiClientError } from "@/lib/api";
import type { MediaFormat, MediaInfo } from "@/types/download";

interface DownloadFormProps {
  onSubmitSuccess: (downloadId: string) => void;
  onSubmitError: (error: string) => void;
  disabled?: boolean;
}

interface FormState {
  url: string;
  error: string | null;
  isLoading: boolean;
}

export function DownloadForm({ onSubmitSuccess, onSubmitError, disabled = false }: DownloadFormProps) {
  const [formState, setFormState] = useState<FormState>({
    url: "",
    error: null,
    isLoading: false,
  });
  const [mediaInfo, setMediaInfo] = useState<MediaInfo | null>(null);
  const [selectedType, setSelectedType] = useState<"video" | "audio">("video");

  /**
   * Handle URL input change with validation
   */
  const handleUrlChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setFormState((prev) => ({
      ...prev,
      url: value,
      error: null,
    }));
  }, []);

  /**
   * Paste URL from clipboard
   */
  const handlePaste = useCallback(async () => {
    try {
      const text = await navigator.clipboard.readText();
      setFormState((prev) => ({
        ...prev,
        url: text.trim(),
        error: null,
      }));
    } catch (err) {
      console.error("Failed to read clipboard:", err);
      setFormState((prev) => ({
        ...prev,
        error: "Unable to access clipboard. Please paste manually.",
      }));
    }
  }, []);

  /**
   * Validate and submit the form
   */
  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();

      // Reset error
      setFormState((prev) => ({ ...prev, error: null }));

      // Client-side validation
      const validation = validateDownloadUrl(formState.url);
      if (!validation.success) {
        setFormState((prev) => ({ ...prev, error: validation.error || "Invalid URL" }));
        return;
      }

      // Start loading state
      setFormState((prev) => ({ ...prev, isLoading: true }));

      try {
        const info = await apiClient.getMediaInfo(formState.url);
        setMediaInfo(info);
        setSelectedType(info.formats.some((item) => item.media_type === "video") ? "video" : "audio");
        setFormState((prev) => ({ ...prev, isLoading: false }));
      } catch (err) {
        let errorMessage = "An unexpected error occurred.";

        if (err instanceof ApiClientError) {
          // Extract error message from API response
          errorMessage =
            (err.data?.error as { message: string })?.message || err.message;
        }

        setFormState({ url: formState.url, error: errorMessage, isLoading: false });
        onSubmitError(errorMessage);
      }
    },
    [formState.url, onSubmitSuccess, onSubmitError]
  );

  const handleFormatDownload = useCallback(async (format: MediaFormat) => {
    setFormState((prev) => ({ ...prev, isLoading: true, error: null }));
    try {
      const response = await apiClient.createDownload({
        url: formState.url,
        format_id: format.format_id,
        media_type: format.media_type,
      });
      onSubmitSuccess(response.id);
      setMediaInfo(null);
      setFormState({ url: "", error: null, isLoading: false });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to start download.";
      setFormState((prev) => ({ ...prev, error: message, isLoading: false }));
      onSubmitError(message);
    }
  }, [formState.url, onSubmitSuccess, onSubmitError]);

  const isSubmitDisabled = !formState.url.trim() || formState.isLoading || disabled;

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      {/* URL Input Group */}
      <div className="space-y-2">
        <label
          htmlFor="download-url"
          className="block text-sm font-medium text-gray-700"
        >
          Download URL
        </label>

        <div className="flex gap-2">
          <div className="relative flex-1">
            <input
              id="download-url"
              type="url"
              value={formState.url}
              onChange={handleUrlChange}
              placeholder="https://example.com/files/application.zip"
              className={cn(
                "block w-full rounded-lg border px-4 py-3 pr-12 text-base",
                "placeholder:text-gray-400",
                "focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20",
                "disabled:bg-gray-50 disabled:text-gray-500",
                formState.error
                  ? "border-red-300 focus:border-red-500 focus:ring-red-500/20"
                  : "border-gray-300"
              )}
              disabled={formState.isLoading || disabled}
              autoComplete="off"
              spellCheck={false}
              aria-describedby={formState.error ? "url-error" : undefined}
              aria-invalid={!!formState.error}
            />

            {/* Paste button inside input */}
            <button
              type="button"
              onClick={handlePaste}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
              title="Paste from clipboard"
              disabled={formState.isLoading || disabled}
              aria-label="Paste URL from clipboard"
            >
              <Clipboard className="h-4 w-4" />
            </button>
          </div>

          {/* Submit button */}
          <button
            type="submit"
            disabled={isSubmitDisabled}
            className={cn(
              "inline-flex items-center gap-2 rounded-lg px-6 py-3 font-medium",
              "transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2",
              isSubmitDisabled
                ? "cursor-not-allowed bg-gray-100 text-gray-400"
                : "bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500"
            )}
            aria-busy={formState.isLoading}
          >
            {formState.isLoading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Starting...
              </>
            ) : (
              <>
                <Download className="h-4 w-4" />
                Get formats
              </>
            )}
          </button>
        </div>

        {/* Error message */}
        {formState.error && (
          <div
            id="url-error"
            className="flex items-start gap-2 text-sm text-red-600"
            role="alert"
          >
            <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
            <span>{formState.error}</span>
          </div>
        )}
      </div>

      {/* Usage notice */}
      <p className="text-xs text-gray-500 leading-relaxed">
        Use public media that you own or are authorized to download. Private,
        protected, and DRM-restricted media is not supported.
      </p>

      {mediaInfo && (
        <div className="rounded-xl border border-blue-200 bg-blue-50/50 p-4 space-y-4">
          <div className="flex gap-3">
            {mediaInfo.thumbnail && (
              <img src={mediaInfo.thumbnail} alt="" className="h-20 w-32 rounded-lg object-cover" />
            )}
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-blue-600">Choose format</p>
              <h3 className="mt-1 font-semibold text-gray-900 line-clamp-2">{mediaInfo.title}</h3>
            </div>
          </div>

          <div className="flex rounded-lg bg-gray-100 p-1">
            {(["video", "audio"] as const).map((type) => {
              const available = mediaInfo.formats.some((item) => item.media_type === type);
              return (
                <button
                  key={type}
                  type="button"
                  disabled={!available}
                  onClick={() => setSelectedType(type)}
                  className={cn(
                    "flex-1 rounded-md px-3 py-2 text-sm font-medium capitalize",
                    selectedType === type ? "bg-white text-blue-700 shadow-sm" : "text-gray-600",
                    !available && "cursor-not-allowed opacity-40"
                  )}
                >
                  {type}
                </button>
              );
            })}
          </div>

          <div className="grid gap-2 sm:grid-cols-2">
            {mediaInfo.formats
              .filter((item) => item.media_type === selectedType)
              .map((format) => (
                <button
                  key={`${format.media_type}-${format.format_id}`}
                  type="button"
                  disabled={formState.isLoading}
                  onClick={() => handleFormatDownload(format)}
                  className="flex items-center justify-between rounded-lg border bg-white px-4 py-3 text-left hover:border-blue-400 hover:bg-blue-50 disabled:opacity-50"
                >
                  <span className="font-medium text-gray-900">{format.label}</span>
                  <span className="text-xs text-gray-500">
                    {format.filesize ? `${(format.filesize / 1048576).toFixed(1)} MB` : ""}
                  </span>
                </button>
              ))}
          </div>

          <button
            type="button"
            onClick={() => setMediaInfo(null)}
            className="text-sm text-gray-600 hover:text-gray-900"
          >
            Cancel
          </button>
        </div>
      )}
    </form>
  );
}

// Import cn utility
import { cn } from "@/lib/utils";

export default DownloadForm;

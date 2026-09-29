"use client";

import { useState, useEffect, useCallback } from "react";
import { Download as DownloadIcon, Shield, AlertCircle, Server, Terminal } from "lucide-react";
import { DownloadForm } from "@/components/DownloadForm";
import { DownloadHistory } from "@/components/DownloadHistory";
import type { Download } from "@/types/download";
import { apiClient, ApiClientError } from "@/lib/api";

/**
 * URL Application Downloader - Main Page
 *
 * Provides a complete interface for downloading files from authorized
 * direct-download URLs with real-time progress tracking.
 */
export default function HomePage() {
  const [downloads, setDownloads] = useState<Download[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [backendAvailable, setBackendAvailable] = useState<boolean | null>(null);
  const [notification, setNotification] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  /**
   * Check if backend is available
   */
  const checkBackendHealth = useCallback(async () => {
    try {
      await apiClient.health();
      setBackendAvailable(true);
      return true;
    } catch (err) {
      setBackendAvailable(false);
      console.error("Backend not available:", err);
      return false;
    }
  }, []);

  /**
   * Load download history on mount and after new downloads
   */
  const loadDownloads = useCallback(async () => {
    setIsLoadingHistory(true);
    
    // First check if backend is available
    const isHealthy = await checkBackendHealth();
    if (!isHealthy) {
      setIsLoadingHistory(false);
      return;
    }

    try {
      const response = await apiClient.listDownloads({ limit: 50 });
      setDownloads(response.downloads);
    } catch (err) {
      console.error("Failed to load downloads:", err);
    } finally {
      setIsLoadingHistory(false);
    }
  }, [checkBackendHealth]);

  // Initial load
  useEffect(() => {
    loadDownloads();
  }, [loadDownloads]);

  /**
   * Handle successful download creation
   */
  const handleDownloadCreated = useCallback((downloadId: string) => {
    showNotification("success", "Download started! Check progress below.");
    loadDownloads();
  }, [loadDownloads]);

  /**
   * Handle download creation error
   */
  const handleDownloadError = useCallback((error: string) => {
    showNotification("error", error);
  }, []);

  /**
   * Handle download removal
   */
  const handleRemove = useCallback((downloadId: string) => {
    setDownloads((prev) => prev.filter((d) => d.id !== downloadId));
  }, []);

  /**
   * Handle retry request
   */
  const handleRetry = useCallback(async (url: string) => {
    try {
      const response = await apiClient.createDownload({ url });
      showNotification("success", "Retry started!");
      loadDownloads();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to start retry";
      showNotification("error", message);
    }
  }, [loadDownloads]);

  /**
   * Show a temporary notification
   */
  const showNotification = useCallback(
    (type: "success" | "error", message: string) => {
      setNotification({ type, message });
      setTimeout(() => setNotification(null), 5000);
    },
    []
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-blue-600 text-white">
              <DownloadIcon className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">
                URL Application Downloader
              </h1>
              <p className="text-sm text-gray-500">
                Download authorized public video or audio
              </p>
            </div>
          </div>
          {backendAvailable === false && (
            <div className="mt-3 flex items-center gap-2 px-3 py-2 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-800">
              <Server className="h-4 w-4 flex-shrink-0" />
              <span>Backend server is not running. Some features may be unavailable.</span>
            </div>
          )}
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-4xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        {/* Notification */}
        {notification && (
          <div
            className={`mb-6 flex items-start gap-3 p-4 rounded-lg ${
              notification.type === "success"
                ? "bg-green-50 text-green-800 border border-green-200"
                : "bg-red-50 text-red-800 border border-red-200"
            }`}
            role="alert"
          >
            {notification.type === "success" ? (
              <DownloadIcon className="h-5 w-5 mt-0.5 flex-shrink-0" />
            ) : (
              <AlertCircle className="h-5 w-5 mt-0.5 flex-shrink-0" />
            )}
            <div className="flex-1">
              <p className="font-medium">
                {notification.type === "success" ? "Success" : "Error"}
              </p>
              <p className="text-sm opacity-90">{notification.message}</p>
            </div>
            <button
              onClick={() => setNotification(null)}
              className="p-1 hover:opacity-70 transition-opacity"
              aria-label="Dismiss notification"
            >
              ✕
            </button>
          </div>
        )}

        {/* Backend Unavailable Notice */}
        {backendAvailable === false && (
          <div className="mb-8 p-6 bg-orange-50 border border-orange-200 rounded-xl">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-6 w-6 text-orange-600 mt-0.5 flex-shrink-0" />
              <div>
                <h2 className="font-semibold text-orange-900 mb-2">Backend Server Required</h2>
                <p className="text-sm text-orange-800 mb-4">
                  The FastAPI backend is not running. To enable full functionality, start the backend server:
                </p>
                <div className="bg-orange-100 rounded-lg p-4 font-mono text-xs overflow-x-auto">
                  <pre className="text-orange-900">{`# Start the backend server:
cd mini-services/url-downloader-backend
source venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Or use Docker:
docker compose up backend`}</pre>
                </div>
                <button
                  onClick={loadDownloads}
                  className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition-colors text-sm"
                >
                  <Terminal className="h-4 w-4" />
                  Retry Connection
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Download form card */}
        <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
          <DownloadForm
            onSubmitSuccess={handleDownloadCreated}
            onSubmitError={handleDownloadError}
            disabled={backendAvailable === false}
          />

          {/* Security notice */}
          <div className="mt-6 pt-5 border-t border-gray-100">
            <div className="flex gap-3 p-3 bg-blue-50 rounded-lg">
              <Shield className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0" />
              <div className="text-sm text-blue-800">
                <p className="font-medium mb-1">Security Notice</p>
                <ul className="space-y-1 text-blue-700/80">
                  <li>• Only public media you own or may download is supported</li>
                  <li>• Private network URLs are blocked for security</li>
                  <li>• All downloads are validated for file type and size</li>
                  <li>• Private, protected, and DRM-restricted media is not supported</li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* Download history */}
        <DownloadHistory
          downloads={downloads}
          onRemove={handleRemove}
          onRetry={handleRetry}
          isLoading={isLoadingHistory}
        />
      </main>

      {/* Footer */}
      <footer className="mt-auto border-t border-gray-200 bg-white">
        <div className="max-w-4xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
          <p className="text-center text-sm text-gray-500">
            URL Application Downloader — Secure file downloading with real-time progress
          </p>
        </div>
      </footer>
    </div>
  );
}

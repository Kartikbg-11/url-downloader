"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  Download as DownloadIcon,
  Loader2,
  LogOut,
  Server,
  Shield,
  UserRound,
} from "lucide-react";
import { DownloadForm } from "@/components/DownloadForm";
import { DownloadHistory } from "@/components/DownloadHistory";
import { LoginForm } from "@/components/LoginForm";
import type { AuthUser, Download } from "@/types/download";
import { apiClient, ApiClientError } from "@/lib/api";

export default function HomePage() {
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [downloads, setDownloads] = useState<Download[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [backendAvailable, setBackendAvailable] = useState<boolean | null>(null);
  const [notification, setNotification] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  const showNotification = useCallback(
    (type: "success" | "error", message: string) => {
      setNotification({ type, message });
      window.setTimeout(() => setNotification(null), 5000);
    },
    []
  );

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

  const loadDownloads = useCallback(async () => {
    setIsLoadingHistory(true);
    try {
      const response = await apiClient.listDownloads({ limit: 50 });
      setDownloads(response.downloads);
    } catch (err) {
      if (err instanceof ApiClientError && err.status === 401) {
        setCurrentUser(null);
        setDownloads([]);
      } else {
        console.error("Failed to load downloads:", err);
        showNotification("error", "Could not load download history.");
      }
    } finally {
      setIsLoadingHistory(false);
    }
  }, [showNotification]);

  const initialize = useCallback(async () => {
    setIsCheckingAuth(true);
    const isHealthy = await checkBackendHealth();
    if (!isHealthy) {
      setCurrentUser(null);
      setIsCheckingAuth(false);
      return;
    }

    try {
      const user = await apiClient.me();
      setCurrentUser(user);
      await loadDownloads();
    } catch (err) {
      if (!(err instanceof ApiClientError && err.status === 401)) {
        console.error("Session check failed:", err);
      }
      setCurrentUser(null);
    } finally {
      setIsCheckingAuth(false);
    }
  }, [checkBackendHealth, loadDownloads]);

  useEffect(() => {
    initialize();
  }, [initialize]);

  const handleLogin = useCallback(
    (user: AuthUser) => {
      setCurrentUser(user);
      showNotification("success", `Signed in as ${user.username}.`);
      loadDownloads();
    },
    [loadDownloads, showNotification]
  );

  const handleLogout = useCallback(async () => {
    setIsLoggingOut(true);
    try {
      await apiClient.logout();
    } catch (err) {
      console.error("Logout request failed:", err);
    } finally {
      setCurrentUser(null);
      setDownloads([]);
      setNotification(null);
      setIsLoggingOut(false);
    }
  }, []);

  const handleDownloadCreated = useCallback(() => {
    showNotification("success", "Download started! Check progress below.");
    loadDownloads();
  }, [loadDownloads, showNotification]);

  const handleDownloadError = useCallback(
    (error: string) => showNotification("error", error),
    [showNotification]
  );

  const handleRemove = useCallback((downloadId: string) => {
    setDownloads((previous) => previous.filter((download) => download.id !== downloadId));
  }, []);

  const handleRetry = useCallback(
    async (url: string) => {
      try {
        await apiClient.createDownload({ url });
        showNotification("success", "Retry started!");
        loadDownloads();
      } catch (err) {
        showNotification(
          "error",
          err instanceof Error ? err.message : "Failed to start retry"
        );
      }
    },
    [loadDownloads, showNotification]
  );

  if (isCheckingAuth) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-950 text-white">
        <div className="text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-blue-400" />
          <p className="mt-4 text-sm text-slate-300">Checking your session...</p>
        </div>
      </main>
    );
  }

  if (!currentUser) {
    return (
      <LoginForm
        backendAvailable={backendAvailable}
        onLogin={handleLogin}
        onRetryConnection={initialize}
      />
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-4xl flex-col gap-4 px-4 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-600 text-white">
              <DownloadIcon className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">URL Application Downloader</h1>
              <p className="text-sm text-gray-500">Your private download workspace</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-700">
              <UserRound className="h-4 w-4" />
              <span className="font-semibold">{currentUser.username}</span>
            </div>
            <button
              type="button"
              onClick={handleLogout}
              disabled={isLoggingOut}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50"
            >
              {isLoggingOut ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <LogOut className="h-4 w-4" />
              )}
              Log out
            </button>
          </div>
        </div>

        {backendAvailable === false && (
          <div className="mx-auto max-w-4xl px-4 pb-4 sm:px-6 lg:px-8">
            <div className="flex items-center gap-2 rounded-lg border border-yellow-200 bg-yellow-50 px-3 py-2 text-sm text-yellow-800">
              <Server className="h-4 w-4 flex-shrink-0" />
              <span>Backend server is not running. Some features may be unavailable.</span>
            </div>
          </div>
        )}
      </header>

      <main className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
        {notification && (
          <div
            className={`mb-6 flex items-start gap-3 rounded-lg border p-4 ${
              notification.type === "success"
                ? "border-green-200 bg-green-50 text-green-800"
                : "border-red-200 bg-red-50 text-red-800"
            }`}
            role="alert"
          >
            {notification.type === "success" ? (
              <DownloadIcon className="mt-0.5 h-5 w-5 flex-shrink-0" />
            ) : (
              <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0" />
            )}
            <div className="flex-1">
              <p className="font-medium">
                {notification.type === "success" ? "Success" : "Error"}
              </p>
              <p className="text-sm opacity-90">{notification.message}</p>
            </div>
            <button
              type="button"
              onClick={() => setNotification(null)}
              className="p-1 transition-opacity hover:opacity-70"
              aria-label="Dismiss notification"
            >
              ×
            </button>
          </div>
        )}

        <section className="mb-8 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <DownloadForm
            onSubmitSuccess={handleDownloadCreated}
            onSubmitError={handleDownloadError}
            disabled={backendAvailable === false}
          />

          <div className="mt-6 border-t border-gray-100 pt-5">
            <div className="flex gap-3 rounded-lg bg-blue-50 p-3">
              <Shield className="mt-0.5 h-5 w-5 flex-shrink-0 text-blue-600" />
              <div className="text-sm text-blue-800">
                <p className="mb-1 font-medium">Security Notice</p>
                <ul className="space-y-1 text-blue-700/80">
                  <li>• Your download history is private to this account</li>
                  <li>• Only public media you own or may download is supported</li>
                  <li>• Private network URLs are blocked for security</li>
                  <li>• Private, protected, and DRM-restricted media is not supported</li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        <DownloadHistory
          downloads={downloads}
          onRemove={handleRemove}
          onRetry={handleRetry}
          isLoading={isLoadingHistory}
        />
      </main>

      <footer className="mt-auto border-t border-gray-200 bg-white">
        <div className="mx-auto max-w-4xl px-4 py-6 sm:px-6 lg:px-8">
          <p className="text-center text-sm text-gray-500">
            URL Application Downloader — Secure downloads with real-time progress
          </p>
        </div>
      </footer>
    </div>
  );
}

/**
 * Custom hook for Server-Sent Events (SSE) progress tracking.
 *
 * Subscribes to SSE endpoint for real-time download progress,
 * handles reconnection, falls back to polling when needed,
 * and cleans up connections on unmount.
 */

"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import type { Download, ProgressEvent, DownloadStatus } from "@/types/download";
import { apiClient } from "@/lib/api";
import { POLLING_INTERVAL, MAX_SSE_RECONNECT_ATTEMPTS, SSE_RECONNECT_DELAY } from "@/lib/config";

interface UseDownloadEventsOptions {
  /** Download ID to track */
  downloadId: string;
  /** Initial download data */
  initialData?: Download;
  /** Callback when download data updates */
  onProgress?: (data: Download) => void;
  /** Callback when terminal state is reached */
  onTerminal?: (status: DownloadStatus) => void;
  /** Callback on error */
  onError?: (error: Error) => void;
}

interface UseDownloadEventsReturn {
  /** Current download data */
  data: Download | null;
  /** Whether currently connected via SSE */
  isConnected: boolean;
  /** Whether using fallback polling mode */
  isPolling: boolean;
  /** Last error encountered */
  error: Error | null;
  /** Manually refresh data */
  refresh: () => Promise<void>;
}

/**
 * Hook for subscribing to download progress events via SSE
 */
export function useDownloadEvents({
  downloadId,
  initialData,
  onProgress,
  onTerminal,
  onError,
}: UseDownloadEventsOptions): UseDownloadEventsReturn {
  const [data, setData] = useState<Download | null>(initialData || null);
  const [isConnected, setIsConnected] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const mountedRef = useRef(true);

  // Store callbacks in refs to avoid re-creating functions
  const callbacksRef = useRef({ onProgress, onTerminal, onError });
  useEffect(() => {
    callbacksRef.current = { onProgress, onTerminal, onError };
  }, [onProgress, onTerminal, onError]);

  /**
   * Stop polling interval
   */
  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    if (mountedRef.current) {
      setIsPolling(false);
    }
  }, []);

  /**
   * Close SSE connection
   */
  const closeConnection = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (mountedRef.current) {
      setIsConnected(false);
    }
  }, []);

  /**
   * Fetch latest download data (used for polling)
   */
  const fetchData = useCallback(async () => {
    try {
      const response = await apiClient.getDownload(downloadId);
      if (mountedRef.current) {
        setData(response);
        setError(null);
        callbacksRef.current.onProgress?.(response);

        // Check for terminal state
        if (
          response.status === "completed" ||
          response.status === "failed" ||
          response.status === "cancelled"
        ) {
          callbacksRef.current.onTerminal?.(response.status);
          stopPolling();
        }
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      if (mountedRef.current) {
        setError(error);
        callbacksRef.current.onError?.(error);
      }
    }
  }, [downloadId, stopPolling]);

  /**
   * Start polling as fallback
   */
  const startPolling = useCallback(() => {
    stopPolling();
    if (!mountedRef.current) return;

    setIsPolling(true);
    fetchData(); // Initial fetch

    pollIntervalRef.current = setInterval(fetchData, POLLING_INTERVAL);
  }, [fetchData, stopPolling]);

  // Main effect: manage connection lifecycle
  useEffect(() => {
    mountedRef.current = true;

    // Cleanup function
    const cleanup = () => {
      mountedRef.current = false;
      closeConnection();
      stopPolling();
    };

    // Don't connect without a valid download ID
    if (!downloadId) {
      return cleanup;
    }

    // Don't connect if already in terminal state
    if (
      data &&
      ["completed", "failed", "cancelled"].includes(data.status)
    ) {
      return cleanup;
    }

    // Don't open duplicate connections
    if (eventSourceRef.current) {
      return cleanup;
    }

    /**
     * Handle SSE message event
     */
    const handleSSEMessage = (event: MessageEvent) => {
      if (!mountedRef.current) return;

      try {
        const eventData: ProgressEvent = JSON.parse(event.data);

        // Handle heartbeat
        if (eventData.type === "heartbeat") {
          return;
        }

        // Update local state
        setData((prev) => {
          const updated = prev
            ? { ...prev, ...eventData }
            : ({ ...eventData } as Download);
          callbacksRef.current.onProgress?.(updated);
          return updated;
        });

        // Handle terminal events
        if (
          eventData.terminal ||
          ["completed", "failed", "cancelled"].includes(eventData.status)
        ) {
          callbacksRef.current.onTerminal?.(eventData.status);
          closeConnection();
          // Do one final fetch to get complete data
          fetchData();
        }
      } catch (err) {
        console.error("[SSE] Failed to parse event:", err);
      }
    };

    /**
     * Handle SSE error event - manages reconnection logic
     */
    const handleSSError = () => {
      if (!mountedRef.current) return;

      console.error("[SSE] Connection error");
      setIsConnected(false);

      // Attempt reconnection
      reconnectAttemptsRef.current += 1;

      if (reconnectAttemptsRef.current <= MAX_SSE_RECONNECT_ATTEMPTS) {
        console.log(
          `[SSE] Reconnection attempt ${reconnectAttemptsRef.current}/${MAX_SSE_RECONNECT_ATTEMPTS}`
        );
        setTimeout(() => {
          if (mountedRef.current && !eventSourceRef.current) {
            // Try reconnecting by creating new EventSource
            attemptReconnect();
          }
        }, SSE_RECONNECT_DELAY);
      } else {
        console.log("[SSE] Max reconnection attempts reached, falling back to polling");
        closeConnection();
        startPolling();
      }
    };

    /**
     * Attempt to create SSE connection or fall back to polling
     */
    const attemptReconnect = () => {
      try {
        const url = apiClient.getEventSourceUrl(downloadId);
        const eventSource = new EventSource(url);

        eventSource.onopen = () => {
          if (!mountedRef.current) return;
          console.log(`[SSE] Connected to events for ${downloadId}`);
          setIsConnected(true);
          setIsPolling(false);
          reconnectAttemptsRef.current = 0;
          setError(null);
        };

        eventSource.onmessage = handleSSEMessage;
        eventSource.onerror = handleSSError;

        eventSourceRef.current = eventSource;
      } catch (err) {
        console.error("[SSE] Failed to create EventSource:", err);
        startPolling();
      }
    };

    // Initial connection attempt
    attemptReconnect();

    return cleanup;
  }, [downloadId, data?.status, closeConnection, stopPolling, startPolling, fetchData]);

  return {
    data,
    isConnected,
    isPolling,
    error,
    refresh: fetchData,
  };
}

export default useDownloadEvents;

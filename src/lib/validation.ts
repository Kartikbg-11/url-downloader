/**
 * URL validation using Zod.
 *
 * Provides client-side URL validation before sending to backend.
 * Backend performs additional security validation.
 */

import { z } from "zod";

/**
 * Zod schema for download URL validation
 */
export const downloadUrlSchema = z
  .string()
  .min(1, "URL cannot be empty")
  .url("Please enter a valid URL")
  .refine(
    (url) => url.startsWith("http://") || url.startsWith("https://"),
    "URL must start with http:// or https://"
  )
  .refine(
    (url) => {
      try {
        const parsed = new URL(url);
        // Must have a valid hostname
        return !!parsed.hostname && parsed.hostname.includes(".");
      } catch {
        return false;
      }
    },
    "URL must contain a valid domain name"
  )
  .refine(
    (url) => !url.includes("localhost") && !url.includes("127.0.0.1"),
    "Localhost URLs are not supported"
  );

/**
 * Type for validated URL input
 */
export type ValidatedUrl = z.infer<typeof downloadUrlSchema>;

/**
 * Validate a download URL
 *
 * @param url - The URL string to validate
 * @returns Result object with success status and data or error
 */
export function validateDownloadUrl(url: string): {
  success: boolean;
  data?: ValidatedUrl;
  error?: string;
} {
  const result = downloadUrlSchema.safeParse(url);

  if (result.success) {
    return { success: true, data: result.data };
  }

  // Get first error message
  const errorMessage = result.error.issues[0]?.message || "Invalid URL";
  return { success: false, error: errorMessage };
}

/**
 * Extract hostname from URL for display
 */
export function extractHostname(url: string): string {
  try {
    const parsed = new URL(url);
    return parsed.hostname;
  } catch {
    return "";
  }
}

/**
 * Extract safe path from URL (without query parameters)
 */
export function extractSafePath(url: string): string {
  try {
    const parsed = new URL(url);
    const path = parsed.pathname;
    // Remove leading slash and get filename if present
    const parts = path.split("/").filter(Boolean);
    return parts.length > 0 ? parts[parts.length - 1] : "";
  } catch {
    return "";
  }
}

import type { Metadata } from "next";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";

export const metadata: Metadata = {
  title: "URL Application Downloader - Secure File Downloads",
  description: "Securely download files from authorized direct-download URLs with real-time progress tracking. Supports APK, EXE, ZIP, PDF, and more.",
  keywords: ["downloader", "file download", "URL downloader", "progressive download", "secure download"],
  authors: [{ name: "URL Downloader Team" }],
  icons: {
    icon: "/favicon.ico",
  },
  openGraph: {
    title: "URL Application Downloader",
    description: "Secure file downloading with real-time progress tracking",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="antialiased bg-background text-foreground">
        {children}
        <Toaster />
      </body>
    </html>
  );
}

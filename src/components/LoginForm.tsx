"use client";

import { FormEvent, useState } from "react";
import { Download, Loader2, LockKeyhole, Server, UserRound } from "lucide-react";
import { apiClient } from "@/lib/api";
import type { AuthUser } from "@/types/download";

interface LoginFormProps {
  backendAvailable: boolean | null;
  onLogin: (user: AuthUser) => void;
  onRetryConnection: () => void;
}

export function LoginForm({
  backendAvailable,
  onLogin,
  onRetryConnection,
}: LoginFormProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const user = await apiClient.login(username.trim(), password);
      onLogin(user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 px-4 py-10 text-slate-900 sm:py-16">
      <div className="mx-auto grid min-h-[calc(100vh-8rem)] max-w-5xl items-center gap-10 lg:grid-cols-[1.05fr_0.95fr]">
        <section className="hidden text-white lg:block">
          <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-600 shadow-lg shadow-blue-950/40">
            <Download className="h-7 w-7" />
          </div>
          <p className="mb-3 text-sm font-semibold uppercase tracking-[0.2em] text-blue-300">
            Private workspace
          </p>
          <h1 className="max-w-xl text-5xl font-bold leading-tight">
            Secure downloads for your account.
          </h1>
          <p className="mt-5 max-w-lg text-lg leading-8 text-slate-300">
            Sign in to submit URLs, follow live progress, and access only the downloads created by you.
          </p>
        </section>

        <section className="rounded-3xl bg-white p-6 shadow-2xl shadow-black/30 sm:p-10">
          <div className="mb-8 lg:hidden">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-blue-600 text-white">
              <Download className="h-6 w-6" />
            </div>
            <h1 className="text-2xl font-bold">URL Application Downloader</h1>
          </div>

          <div className="mb-7">
            <p className="text-sm font-semibold text-blue-600">Welcome back</p>
            <h2 className="mt-1 text-3xl font-bold tracking-tight">Sign in</h2>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              Use one of the three accounts configured by the administrator.
            </p>
          </div>

          {backendAvailable === false && (
            <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              <div className="flex gap-3">
                <Server className="mt-0.5 h-5 w-5 flex-none" />
                <div>
                  <p className="font-semibold">Backend is not available</p>
                  <p className="mt-1 text-amber-800">Start the FastAPI service, then try again.</p>
                  <button
                    type="button"
                    onClick={onRetryConnection}
                    className="mt-3 font-semibold text-amber-950 underline underline-offset-4"
                  >
                    Retry connection
                  </button>
                </div>
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="username" className="mb-2 block text-sm font-semibold text-slate-700">
                Username
              </label>
              <div className="relative">
                <UserRound className="pointer-events-none absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
                <input
                  id="username"
                  name="username"
                  autoComplete="username"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  placeholder="Enter your username"
                  required
                  className="w-full rounded-xl border border-slate-300 py-3 pl-11 pr-4 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
                />
              </div>
            </div>

            <div>
              <label htmlFor="password" className="mb-2 block text-sm font-semibold text-slate-700">
                Password
              </label>
              <div className="relative">
                <LockKeyhole className="pointer-events-none absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
                <input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Enter your password"
                  required
                  className="w-full rounded-xl border border-slate-300 py-3 pl-11 pr-4 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
                />
              </div>
            </div>

            {error && (
              <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={isSubmitting || backendAvailable === false}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSubmitting && <Loader2 className="h-5 w-5 animate-spin" />}
              {isSubmitting ? "Signing in..." : "Sign in"}
            </button>
          </form>

          <div className="mt-7 rounded-xl bg-slate-50 p-4 text-xs leading-5 text-slate-500">
            Default local usernames: <span className="font-semibold text-slate-700">user1, user2, user3</span>.
            Passwords are controlled by the backend <span className="font-mono">AUTH_USERS</span> setting.
          </div>
        </section>
      </div>
    </main>
  );
}

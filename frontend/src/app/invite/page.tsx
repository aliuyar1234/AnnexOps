"use client";

import { AppShell } from "@/components/layout/app-shell";
import { ApiError, apiRequest } from "@/lib/http";
import type { AcceptInviteResponse } from "@/lib/types";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, type FormEvent } from "react";

function InvitePageInner() {
  const router = useRouter();
  const params = useSearchParams();
  const tokenFromUrl = params.get("token");

  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AcceptInviteResponse | null>(null);

  useEffect(() => {
    if (tokenFromUrl) setToken(tokenFromUrl);
  }, [tokenFromUrl]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setIsSubmitting(true);
    try {
      const response = await apiRequest<AcceptInviteResponse>("/api/auth/accept-invite", {
        method: "POST",
        body: JSON.stringify({ token: token.trim(), password }),
      });
      setResult(response);
      setPassword("");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? "Invite acceptance failed. Check token and password rules."
          : "Unexpected error.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-md rounded-xl border border-zinc-200 bg-white p-6">
      <h1 className="text-lg font-semibold tracking-tight">Accept invitation</h1>
      <p className="mt-1 text-sm text-zinc-600">Create your account using the invitation token.</p>

        {result ? (
          <div className="mt-6 space-y-3">
            <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
              Account created for <span className="font-mono">{result.email}</span>.
            </div>
            <button
              type="button"
              onClick={() => router.push("/login")}
              className="w-full rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800"
            >
              Continue to login
            </button>
          </div>
        ) : (
          <form className="mt-6 space-y-4" onSubmit={onSubmit}>
            <div>
              <label className="text-sm font-medium">Invitation token</label>
              <input
                value={token}
                onChange={(e) => setToken(e.target.value)}
                required
                className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 font-mono text-xs outline-none focus:border-zinc-400"
              />
            </div>

            <div>
              <label className="text-sm font-medium">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                autoComplete="new-password"
              />
              <p className="mt-1 text-xs text-zinc-500">
                Must meet backend password rules (length + upper/lower/digit/special).
              </p>
            </div>

            {error ? (
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </div>
            ) : null}

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSubmitting ? "Creating…" : "Create account"}
            </button>

            <div className="text-center text-xs text-zinc-500">
              Already have an account?{" "}
              <Link href="/login" className="underline hover:text-zinc-700">
                Sign in
              </Link>
            </div>
          </form>
        )}
    </div>
  );
}

export default function InvitePage() {
  return (
    <AppShell>
      <Suspense
        fallback={
          <div className="flex min-h-[40vh] items-center justify-center text-sm text-zinc-600">
            Loading…
          </div>
        }
      >
        <InvitePageInner />
      </Suspense>
    </AppShell>
  );
}

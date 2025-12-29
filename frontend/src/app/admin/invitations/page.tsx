"use client";

import { useAuth } from "@/components/auth/auth-provider";
import { RequireRole } from "@/components/auth/require-role";
import { AppShell } from "@/components/layout/app-shell";
import { ApiError, apiRequest } from "@/lib/http";
import type { InvitationResponse } from "@/lib/types";
import Link from "next/link";
import { useMemo, useState, type FormEvent } from "react";

const ROLES = ["viewer", "reviewer", "editor", "admin"] as const;

export default function AdminInvitationsPage() {
  const { accessToken } = useAuth();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<(typeof ROLES)[number]>("viewer");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [invitation, setInvitation] = useState<InvitationResponse | null>(null);

  const acceptLink = useMemo(() => {
    if (!invitation) return null;
    return `/invite?token=${encodeURIComponent(invitation.token)}`;
  }, [invitation]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setInvitation(null);
    if (!accessToken) return;

    setIsSubmitting(true);
    try {
      const result = await apiRequest<InvitationResponse>(
        "/api/auth/invite",
        {
          method: "POST",
          body: JSON.stringify({ email: email.trim(), role }),
        },
        { accessToken },
      );
      setInvitation(result);
      setEmail("");
      setRole("viewer");
    } catch (err) {
      setError(err instanceof ApiError ? "Invitation failed." : "Unexpected error.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AppShell>
      <RequireRole role="admin">
        <h1 className="text-xl font-semibold tracking-tight">Invitations</h1>
        <p className="mt-2 text-sm text-zinc-600">Invite users into your organization.</p>

        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <div className="rounded-xl border border-zinc-200 bg-white p-6">
            <h2 className="text-sm font-medium">Create invitation</h2>

            <form className="mt-4 space-y-4" onSubmit={onSubmit}>
              <div>
                <label className="text-sm font-medium">Email</label>
                <input
                  required
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  placeholder="user@company.com"
                />
              </div>

              <div>
                <label className="text-sm font-medium">Role</label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value as (typeof ROLES)[number])}
                  className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              </div>

              {error ? (
                <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {error}
                </div>
              ) : null}

              <button
                type="submit"
                disabled={isSubmitting}
                className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSubmitting ? "Creating…" : "Create invitation"}
              </button>
            </form>
          </div>

          <div className="rounded-xl border border-zinc-200 bg-white p-6">
            <h2 className="text-sm font-medium">Share</h2>
            <p className="mt-1 text-xs text-zinc-600">
              Invitation tokens are secrets. Share them via a secure channel.
            </p>

            {invitation ? (
              <div className="mt-4 space-y-3 text-sm">
                <div>
                  <div className="text-xs text-zinc-500">Token</div>
                  <div className="mt-1 break-all rounded-md border border-zinc-200 bg-zinc-50 p-3 font-mono text-xs">
                    {invitation.token}
                  </div>
                </div>

                {acceptLink ? (
                  <div>
                    <div className="text-xs text-zinc-500">Accept link</div>
                    <Link
                      href={acceptLink}
                      className="mt-1 inline-flex break-all rounded-md border border-zinc-200 bg-white px-3 py-2 text-xs hover:bg-zinc-50"
                    >
                      {acceptLink}
                    </Link>
                  </div>
                ) : null}

                <div className="text-xs text-zinc-500">
                  Expires at: <span className="font-mono">{invitation.expires_at}</span>
                </div>
              </div>
            ) : (
              <div className="mt-4 text-sm text-zinc-600">Create an invitation to view its token.</div>
            )}
          </div>
        </div>
      </RequireRole>
    </AppShell>
  );
}


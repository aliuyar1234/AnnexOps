"use client";

import { RequireRole } from "@/components/auth/require-role";
import { AppShell } from "@/components/layout/app-shell";
import Link from "next/link";

export default function AdminHomePage() {
  return (
    <AppShell>
      <RequireRole role="admin">
        <h1 className="text-xl font-semibold tracking-tight">Admin</h1>
        <p className="mt-2 text-sm text-zinc-600">
          Organization settings, users, and invitations.
        </p>

        <div className="mt-6 grid gap-3 sm:grid-cols-3">
          <Link
            href="/admin/organization"
            className="rounded-xl border border-zinc-200 bg-white p-4 hover:bg-zinc-50"
          >
            <div className="text-sm font-medium">Organization</div>
            <div className="mt-1 text-xs text-zinc-600">Name and basics</div>
          </Link>
          <Link
            href="/admin/users"
            className="rounded-xl border border-zinc-200 bg-white p-4 hover:bg-zinc-50"
          >
            <div className="text-sm font-medium">Users</div>
            <div className="mt-1 text-xs text-zinc-600">Roles and access</div>
          </Link>
          <Link
            href="/admin/invitations"
            className="rounded-xl border border-zinc-200 bg-white p-4 hover:bg-zinc-50"
          >
            <div className="text-sm font-medium">Invitations</div>
            <div className="mt-1 text-xs text-zinc-600">Invite new members</div>
          </Link>
          <Link
            href="/admin/llm"
            className="rounded-xl border border-zinc-200 bg-white p-4 hover:bg-zinc-50"
          >
            <div className="text-sm font-medium">LLM</div>
            <div className="mt-1 text-xs text-zinc-600">Status and config</div>
          </Link>
        </div>
      </RequireRole>
    </AppShell>
  );
}

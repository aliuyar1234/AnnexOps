"use client";

import { useAuth } from "@/components/auth/auth-provider";
import { AppShell } from "@/components/layout/app-shell";
import Link from "next/link";

export default function Home() {
  const { user } = useAuth();

  return (
    <AppShell>
      <div className="rounded-xl border border-zinc-200 bg-white p-6">
        <h1 className="text-2xl font-semibold tracking-tight">Evidence-Pack-as-Code</h1>
        <p className="mt-2 text-sm text-zinc-600">
          AnnexOps helps teams build auditable evidence packs for EU AI Act compliance.
        </p>

        <div className="mt-6 text-sm">
          <span className="font-medium">Status:</span>{" "}
          {user ? (
            <span className="text-zinc-800">
              signed in as <span className="font-mono">{user.email}</span> ({user.role})
            </span>
          ) : (
            <span className="text-zinc-800">not signed in</span>
          )}
        </div>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          <Link
            href="/systems"
            className="inline-flex items-center justify-center rounded-md border border-zinc-200 bg-white px-4 py-2 text-sm hover:bg-zinc-50"
          >
            Open systems
          </Link>
          <Link
            href="/evidence"
            className="inline-flex items-center justify-center rounded-md border border-zinc-200 bg-white px-4 py-2 text-sm hover:bg-zinc-50"
          >
            Open evidence
          </Link>
          {!user ? (
            <Link
              href="/login"
              className="inline-flex items-center justify-center rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800"
            >
              Login
            </Link>
          ) : null}
        </div>
      </div>
    </AppShell>
  );
}


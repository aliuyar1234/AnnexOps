"use client";

import { RequireAuth } from "@/components/auth/require-auth";
import { AppShell } from "@/components/layout/app-shell";

export default function EvidencePage() {
  return (
    <AppShell>
      <RequireAuth>
        <h1 className="text-xl font-semibold tracking-tight">Evidence</h1>
        <p className="mt-2 text-sm text-zinc-600">
          UI for creating and mapping evidence will live here.
        </p>
      </RequireAuth>
    </AppShell>
  );
}


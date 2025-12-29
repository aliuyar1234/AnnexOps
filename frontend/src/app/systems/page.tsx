"use client";

import { RequireAuth } from "@/components/auth/require-auth";
import { AppShell } from "@/components/layout/app-shell";

export default function SystemsPage() {
  return (
    <AppShell>
      <RequireAuth>
        <h1 className="text-xl font-semibold tracking-tight">Systems</h1>
        <p className="mt-2 text-sm text-zinc-600">
          UI for the Systems registry will live here.
        </p>
      </RequireAuth>
    </AppShell>
  );
}


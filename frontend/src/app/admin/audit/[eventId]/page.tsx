"use client";

import { RequireRole } from "@/components/auth/require-role";
import { AppShell } from "@/components/layout/app-shell";
import { ApiError, apiRequest } from "@/lib/http";
import type { AuditEventDetailResponse } from "@/lib/types";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

export default function AuditEventDetailPage() {
  const { eventId } = useParams<{ eventId: string }>();

  const [event, setEvent] = useState<AuditEventDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const prettyDiff = useMemo(() => {
    if (!event) return "";
    try {
      return JSON.stringify(event.diff_json, null, 2);
    } catch {
      return String(event.diff_json);
    }
  }, [event]);

  useEffect(() => {
    let isMounted = true;
    (async () => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await apiRequest<AuditEventDetailResponse>(`/api/admin/audit/events/${eventId}`);
        if (isMounted) setEvent(data);
      } catch (err) {
        if (isMounted) setError(err instanceof ApiError ? "Failed to load audit event." : "Unexpected error.");
      } finally {
        if (isMounted) setIsLoading(false);
      }
    })();
    return () => {
      isMounted = false;
    };
  }, [eventId]);

  return (
    <AppShell>
      <RequireRole role="admin">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Audit event</h1>
            <div className="mt-1 text-xs text-zinc-500">
              <Link href="/admin/audit" className="hover:underline">
                Audit log
              </Link>{" "}
              / <span className="font-mono">{eventId}</span>
            </div>
          </div>
        </div>

        {isLoading ? (
          <div className="mt-6 text-sm text-zinc-600">Loading…</div>
        ) : error ? (
          <div className="mt-6 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : !event ? (
          <div className="mt-6 text-sm text-zinc-600">Not found.</div>
        ) : (
          <div className="mt-6 grid gap-6 lg:grid-cols-3">
            <div className="space-y-4 lg:col-span-1">
              <div className="rounded-xl border border-zinc-200 bg-white p-6">
                <div className="text-xs text-zinc-500">Time</div>
                <div className="mt-1 font-mono text-sm">{event.created_at}</div>

                <div className="mt-4 text-xs text-zinc-500">User</div>
                <div className="mt-1 text-sm">{event.user ? event.user.email : "system"}</div>

                <div className="mt-4 text-xs text-zinc-500">Action</div>
                <div className="mt-1 font-mono text-sm">{event.action}</div>

                <div className="mt-4 text-xs text-zinc-500">Entity</div>
                <div className="mt-1 text-xs text-zinc-700">{event.entity_type}</div>
                <div className="mt-1 font-mono text-xs text-zinc-500">{event.entity_id}</div>

                <div className="mt-4 text-xs text-zinc-500">IP</div>
                <div className="mt-1 font-mono text-xs text-zinc-600">{event.ip_address ?? "—"}</div>
              </div>
            </div>

            <div className="lg:col-span-2">
              <div className="rounded-xl border border-zinc-200 bg-white p-6">
                <h2 className="text-sm font-medium">Diff / metadata</h2>
                {event.diff_json ? (
                  <pre className="mt-3 overflow-auto rounded-md border border-zinc-200 bg-zinc-50 p-3 text-xs">
                    <code>{prettyDiff}</code>
                  </pre>
                ) : (
                  <div className="mt-3 text-sm text-zinc-600">No diff data.</div>
                )}
              </div>
            </div>
          </div>
        )}
      </RequireRole>
    </AppShell>
  );
}


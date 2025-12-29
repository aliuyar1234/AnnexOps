"use client";

import { useAuth } from "@/components/auth/auth-provider";
import { RequireAuth } from "@/components/auth/require-auth";
import { AppShell } from "@/components/layout/app-shell";
import { ApiError, apiRequest } from "@/lib/http";
import type { DecisionLogDetailResponse } from "@/lib/types";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

export default function DecisionLogDetailPage() {
  const { systemId, versionId, logId } = useParams<{ systemId: string; versionId: string; logId: string }>();
  const { accessToken } = useAuth();

  const [log, setLog] = useState<DecisionLogDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const prettyJson = useMemo(() => {
    if (!log) return "";
    try {
      return JSON.stringify(log.event_json, null, 2);
    } catch {
      return String(log.event_json);
    }
  }, [log]);

  useEffect(() => {
    let isMounted = true;
    (async () => {
      if (!accessToken) return;
      setIsLoading(true);
      setError(null);
      try {
        const data = await apiRequest<DecisionLogDetailResponse>(
          `/api/systems/${systemId}/versions/${versionId}/logs/${logId}`,
          {},
          { accessToken },
        );
        if (isMounted) setLog(data);
      } catch (err) {
        if (isMounted) setError(err instanceof ApiError ? "Failed to load log entry." : "Unexpected error.");
      } finally {
        if (isMounted) setIsLoading(false);
      }
    })();
    return () => {
      isMounted = false;
    };
  }, [accessToken, logId, systemId, versionId]);

  return (
    <AppShell>
      <RequireAuth>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Log entry</h1>
            <div className="mt-1 text-xs text-zinc-500">
              <Link href={`/systems/${systemId}/versions/${versionId}/decision-logs`} className="hover:underline">
                Decision logs
              </Link>{" "}
              / <span className="font-mono">{logId}</span>
            </div>
          </div>
        </div>

        {isLoading ? (
          <div className="mt-6 text-sm text-zinc-600">Loading…</div>
        ) : error ? (
          <div className="mt-6 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : !log ? (
          <div className="mt-6 text-sm text-zinc-600">Not found.</div>
        ) : (
          <div className="mt-6 grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-1 space-y-4">
              <div className="rounded-xl border border-zinc-200 bg-white p-6">
                <div className="text-xs text-zinc-500">Event time</div>
                <div className="mt-1 font-mono text-sm">{log.event_time}</div>
                <div className="mt-3 text-xs text-zinc-500">Actor</div>
                <div className="mt-1 text-sm">{log.actor || "—"}</div>
                <div className="mt-3 text-xs text-zinc-500">Ingested</div>
                <div className="mt-1 font-mono text-sm">{log.ingested_at}</div>
                <div className="mt-3 text-xs text-zinc-500">Event ID</div>
                <div className="mt-1 font-mono text-xs text-zinc-600">{log.event_id}</div>
              </div>
            </div>
            <div className="lg:col-span-2">
              <div className="rounded-xl border border-zinc-200 bg-white p-6">
                <h2 className="text-sm font-medium">Raw event JSON</h2>
                <pre className="mt-3 overflow-auto rounded-md border border-zinc-200 bg-zinc-50 p-3 text-xs">
                  <code>{prettyJson}</code>
                </pre>
              </div>
            </div>
          </div>
        )}
      </RequireAuth>
    </AppShell>
  );
}


"use client";

import { useAuth } from "@/components/auth/auth-provider";
import { RequireAuth } from "@/components/auth/require-auth";
import { AppShell } from "@/components/layout/app-shell";
import { ApiError, apiRequest } from "@/lib/http";
import type { DecisionLogListResponse } from "@/lib/types";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

export default function DecisionLogsPage() {
  const { systemId, versionId } = useParams<{ systemId: string; versionId: string }>();
  const { accessToken } = useAuth();

  const [logs, setLogs] = useState<DecisionLogListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [limit] = useState(50);
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    let isMounted = true;
    (async () => {
      if (!accessToken) return;
      setIsLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        params.set("limit", String(limit));
        params.set("offset", String(offset));
        const data = await apiRequest<DecisionLogListResponse>(
          `/api/systems/${systemId}/versions/${versionId}/logs?${params.toString()}`,
          {},
          { accessToken },
        );
        if (isMounted) setLogs(data);
      } catch (err) {
        if (isMounted) {
          setError(err instanceof ApiError ? "Failed to load decision logs." : "Unexpected error.");
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    })();
    return () => {
      isMounted = false;
    };
  }, [accessToken, limit, offset, systemId, versionId]);

  const canPrev = offset > 0;
  const canNext = logs ? offset + logs.items.length < logs.total : false;

  return (
    <AppShell>
      <RequireAuth>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Decision logs</h1>
            <div className="mt-1 text-xs text-zinc-500">
              <Link href={`/systems/${systemId}/versions/${versionId}`} className="hover:underline">
                Version
              </Link>{" "}
              / decision logs
            </div>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={!canPrev || isLoading}
              onClick={() => setOffset((o) => Math.max(0, o - limit))}
              className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Prev
            </button>
            <button
              type="button"
              disabled={!canNext || isLoading}
              onClick={() => setOffset((o) => o + limit)}
              className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Next
            </button>
          </div>
        </div>

        {isLoading ? (
          <div className="mt-6 text-sm text-zinc-600">Loading…</div>
        ) : error ? (
          <div className="mt-6 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : !logs ? (
          <div className="mt-6 text-sm text-zinc-600">Not found.</div>
        ) : logs.items.length === 0 ? (
          <div className="mt-6 rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-600">
            No logs yet.
          </div>
        ) : (
          <div className="mt-6 overflow-auto rounded-xl border border-zinc-200 bg-white">
            <table className="w-full text-sm">
              <thead className="border-b border-zinc-200 bg-zinc-50 text-xs text-zinc-600">
                <tr>
                  <th className="px-3 py-2 text-left">Event time</th>
                  <th className="px-3 py-2 text-left">Actor</th>
                  <th className="px-3 py-2 text-left">Decision</th>
                  <th className="px-3 py-2 text-left">Ingested</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {logs.items.map((l) => (
                  <tr key={l.id} className="hover:bg-zinc-50">
                    <td className="px-3 py-2 whitespace-nowrap font-mono text-xs text-zinc-700">
                      <Link
                        href={`/systems/${systemId}/versions/${versionId}/decision-logs/${l.id}`}
                        className="hover:underline"
                      >
                        {l.event_time}
                      </Link>
                    </td>
                    <td className="px-3 py-2">{l.actor || "—"}</td>
                    <td className="px-3 py-2">{l.decision ?? "—"}</td>
                    <td className="px-3 py-2 whitespace-nowrap font-mono text-xs text-zinc-500">
                      {l.ingested_at}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {logs ? (
          <div className="mt-4 text-xs text-zinc-500">
            showing <span className="font-mono">{logs.items.length}</span> of{" "}
            <span className="font-mono">{logs.total}</span> (offset{" "}
            <span className="font-mono">{offset}</span>)
          </div>
        ) : null}
      </RequireAuth>
    </AppShell>
  );
}


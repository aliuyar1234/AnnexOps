"use client";

import { RequireRole } from "@/components/auth/require-role";
import { AppShell } from "@/components/layout/app-shell";
import { ApiError, apiRequest } from "@/lib/http";
import type { AuditEventListResponse } from "@/lib/types";
import Link from "next/link";
import { useEffect, useMemo, useState, type FormEvent } from "react";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function isUuid(value: string): boolean {
  return UUID_RE.test(value.trim());
}

export default function AuditLogPage() {
  const [filters, setFilters] = useState({
    action: "",
    entityType: "",
    entityId: "",
    userId: "",
    startTime: "",
    endTime: "",
  });

  const [applied, setApplied] = useState(filters);

  const [limit] = useState(50);
  const [offset, setOffset] = useState(0);

  const [data, setData] = useState<AuditEventListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const params = useMemo(() => {
    const p = new URLSearchParams();
    p.set("limit", String(limit));
    p.set("offset", String(offset));

    if (applied.action.trim()) p.set("action", applied.action.trim());
    if (applied.entityType.trim()) p.set("entity_type", applied.entityType.trim());
    if (applied.entityId.trim()) p.set("entity_id", applied.entityId.trim());
    if (applied.userId.trim()) p.set("user_id", applied.userId.trim());
    if (applied.startTime) p.set("start_time", new Date(applied.startTime).toISOString());
    if (applied.endTime) p.set("end_time", new Date(applied.endTime).toISOString());
    return p;
  }, [applied, limit, offset]);

  useEffect(() => {
    let isMounted = true;
    (async () => {
      setIsLoading(true);
      setError(null);
      try {
        const result = await apiRequest<AuditEventListResponse>(`/api/admin/audit/events?${params.toString()}`);
        if (isMounted) setData(result);
      } catch (err) {
        if (isMounted) setError(err instanceof ApiError ? "Failed to load audit log." : "Unexpected error.");
      } finally {
        if (isMounted) setIsLoading(false);
      }
    })();
    return () => {
      isMounted = false;
    };
  }, [params]);

  function onApply(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (filters.entityId.trim() && !isUuid(filters.entityId)) {
      setError("entity_id must be a UUID.");
      return;
    }
    if (filters.userId.trim() && !isUuid(filters.userId)) {
      setError("user_id must be a UUID.");
      return;
    }

    setOffset(0);
    setApplied(filters);
  }

  const canPrev = offset > 0;
  const canNext = data ? offset + data.items.length < data.total : false;

  return (
    <AppShell>
      <RequireRole role="admin">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Audit log</h1>
            <div className="mt-1 text-xs text-zinc-500">
              <Link href="/admin" className="hover:underline">
                Admin
              </Link>{" "}
              / audit
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

        <div className="mt-6 rounded-xl border border-zinc-200 bg-white p-6">
          <h2 className="text-sm font-medium">Filters</h2>
          <form className="mt-4 grid gap-3 sm:grid-cols-2" onSubmit={onApply}>
            <div>
              <label className="text-xs font-medium">Action (exact)</label>
              <input
                value={filters.action}
                onChange={(e) => setFilters((f) => ({ ...f, action: e.target.value }))}
                className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                placeholder="e.g. evidence.update"
              />
            </div>
            <div>
              <label className="text-xs font-medium">Entity type</label>
              <input
                value={filters.entityType}
                onChange={(e) => setFilters((f) => ({ ...f, entityType: e.target.value }))}
                className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                placeholder="e.g. evidence_item"
              />
            </div>
            <div>
              <label className="text-xs font-medium">Entity ID (UUID)</label>
              <input
                value={filters.entityId}
                onChange={(e) => setFilters((f) => ({ ...f, entityId: e.target.value }))}
                className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 font-mono text-xs outline-none focus:border-zinc-400"
                placeholder="00000000-0000-0000-0000-000000000000"
              />
            </div>
            <div>
              <label className="text-xs font-medium">User ID (UUID)</label>
              <input
                value={filters.userId}
                onChange={(e) => setFilters((f) => ({ ...f, userId: e.target.value }))}
                className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 font-mono text-xs outline-none focus:border-zinc-400"
                placeholder="00000000-0000-0000-0000-000000000000"
              />
            </div>
            <div>
              <label className="text-xs font-medium">Start time</label>
              <input
                type="datetime-local"
                value={filters.startTime}
                onChange={(e) => setFilters((f) => ({ ...f, startTime: e.target.value }))}
                className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
              />
            </div>
            <div>
              <label className="text-xs font-medium">End time</label>
              <input
                type="datetime-local"
                value={filters.endTime}
                onChange={(e) => setFilters((f) => ({ ...f, endTime: e.target.value }))}
                className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
              />
            </div>
            <div className="sm:col-span-2 flex items-center justify-between gap-3">
              <button
                type="submit"
                className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800"
              >
                Apply
              </button>
              {data ? (
                <div className="text-xs text-zinc-500">
                  total: <span className="font-mono">{data.total}</span> · offset:{" "}
                  <span className="font-mono">{offset}</span>
                </div>
              ) : null}
            </div>
          </form>
        </div>

        {error ? (
          <div className="mt-6 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        {isLoading ? (
          <div className="mt-6 text-sm text-zinc-600">Loading…</div>
        ) : data && data.items.length > 0 ? (
          <div className="mt-6 overflow-auto rounded-xl border border-zinc-200 bg-white">
            <table className="w-full text-sm">
              <thead className="border-b border-zinc-200 bg-zinc-50 text-xs text-zinc-600">
                <tr>
                  <th className="px-3 py-2 text-left">Time</th>
                  <th className="px-3 py-2 text-left">User</th>
                  <th className="px-3 py-2 text-left">Action</th>
                  <th className="px-3 py-2 text-left">Entity</th>
                  <th className="px-3 py-2 text-left">IP</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {data.items.map((ev) => (
                  <tr key={ev.id} className="hover:bg-zinc-50">
                    <td className="px-3 py-2 whitespace-nowrap font-mono text-xs text-zinc-700">
                      <Link href={`/admin/audit/${ev.id}`} className="hover:underline">
                        {ev.created_at}
                      </Link>
                    </td>
                    <td className="px-3 py-2">
                      {ev.user ? (
                        <span className="text-sm">
                          {ev.user.email}{" "}
                          <span className="ml-2 rounded-full border border-zinc-200 bg-white px-2 py-0.5 text-xs text-zinc-600">
                            {ev.user.role}
                          </span>
                        </span>
                      ) : (
                        <span className="text-sm text-zinc-500">system</span>
                      )}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">{ev.action}</td>
                    <td className="px-3 py-2">
                      <div className="text-xs text-zinc-600">{ev.entity_type}</div>
                      <div className="font-mono text-xs text-zinc-500">{ev.entity_id}</div>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-zinc-600">{ev.ip_address ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : data ? (
          <div className="mt-6 rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-600">
            No events found.
          </div>
        ) : null}
      </RequireRole>
    </AppShell>
  );
}


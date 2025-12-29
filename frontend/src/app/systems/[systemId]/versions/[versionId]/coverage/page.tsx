"use client";

import { useAuth } from "@/components/auth/auth-provider";
import { RequireAuth } from "@/components/auth/require-auth";
import { AppShell } from "@/components/layout/app-shell";
import { ApiError, apiRequest } from "@/lib/http";
import type { CompletenessResponse } from "@/lib/types";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

export default function VersionCoveragePage() {
  const { systemId, versionId } = useParams<{ systemId: string; versionId: string }>();
  const { accessToken } = useAuth();

  const [completeness, setCompleteness] = useState<CompletenessResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let isMounted = true;
    (async () => {
      if (!accessToken) return;
      setIsLoading(true);
      setError(null);
      try {
        const data = await apiRequest<CompletenessResponse>(
          `/api/systems/${systemId}/versions/${versionId}/completeness`,
          {},
          { accessToken },
        );
        if (isMounted) setCompleteness(data);
      } catch (err) {
        if (isMounted) {
          setError(err instanceof ApiError ? "Failed to load coverage." : "Unexpected error.");
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    })();
    return () => {
      isMounted = false;
    };
  }, [accessToken, systemId, versionId]);

  const filtered = useMemo(() => {
    if (!completeness) return [];
    const q = query.trim().toLowerCase();
    if (!q) return completeness.sections;
    return completeness.sections.filter(
      (s) => s.section_key.toLowerCase().includes(q) || s.title.toLowerCase().includes(q),
    );
  }, [completeness, query]);

  return (
    <AppShell>
      <RequireAuth>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Coverage</h1>
            <div className="mt-1 text-xs text-zinc-500">
              <Link href={`/systems/${systemId}/versions/${versionId}`} className="hover:underline">
                Version
              </Link>{" "}
              / mapping overview
            </div>
          </div>
          {completeness ? (
            <div className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm">
              Overall: <span className="font-mono">{Math.round(completeness.overall_score)}%</span>
            </div>
          ) : null}
        </div>

        <div className="mt-6">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search sections…"
            className="w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
          />
        </div>

        {isLoading ? (
          <div className="mt-6 text-sm text-zinc-600">Loading…</div>
        ) : error ? (
          <div className="mt-6 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : !completeness ? (
          <div className="mt-6 text-sm text-zinc-600">Not found.</div>
        ) : (
          <div className="mt-6 space-y-3">
            {filtered.map((s) => {
              const fields = Object.keys(s.field_completion ?? {}).sort();
              const completeCount = fields.filter((f) => s.field_completion[f]).length;
              const totalCount = fields.length;

              return (
                <div key={s.section_key} className="rounded-xl border border-zinc-200 bg-white p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <Link
                        href={`/systems/${systemId}/versions/${versionId}/sections/${encodeURIComponent(
                          s.section_key,
                        )}`}
                        className="text-sm font-semibold hover:underline"
                      >
                        {s.title}
                      </Link>
                      <div className="mt-1 text-xs text-zinc-500 font-mono">{s.section_key}</div>
                    </div>
                    <div className="text-right text-xs text-zinc-600">
                      <div>
                        score: <span className="font-mono">{Math.round(s.score)}%</span>
                      </div>
                      <div>
                        evidence: <span className="font-mono">{s.evidence_count}</span>
                      </div>
                      <div>
                        fields:{" "}
                        <span className="font-mono">
                          {completeCount}/{totalCount || 0}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 flex items-center gap-3">
                    <div className="h-2 w-56 overflow-hidden rounded-full bg-zinc-100">
                      <div
                        className="h-full bg-zinc-900"
                        style={{ width: `${Math.max(0, Math.min(100, s.score))}%` }}
                      />
                    </div>
                    <div className="text-xs text-zinc-600">
                      <span className="font-mono">{Math.round(s.score)}%</span>
                    </div>
                  </div>

                  {fields.length > 0 ? (
                    <div className="mt-4 flex flex-wrap gap-1">
                      {fields.map((f) => {
                        const ok = Boolean(s.field_completion[f]);
                        return (
                          <span
                            key={f}
                            title={`${f}: ${ok ? "complete" : "missing"}`}
                            className={`h-2.5 w-2.5 rounded-sm border ${
                              ok ? "border-emerald-300 bg-emerald-500" : "border-red-200 bg-red-300"
                            }`}
                          />
                        );
                      })}
                    </div>
                  ) : (
                    <div className="mt-4 text-xs text-zinc-500">No required fields for this section.</div>
                  )}

                  {s.gaps.length > 0 ? (
                    <div className="mt-4">
                      <div className="text-xs font-medium text-zinc-700">Gaps</div>
                      <ul className="mt-2 space-y-1 text-xs text-zinc-600">
                        {s.gaps.slice(0, 6).map((g, idx) => (
                          <li key={`${s.section_key}-${idx}`} className="rounded-md bg-zinc-50 px-2 py-1">
                            {g}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              );
            })}
            {filtered.length === 0 ? (
              <div className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-600">
                No matches.
              </div>
            ) : null}
          </div>
        )}
      </RequireAuth>
    </AppShell>
  );
}


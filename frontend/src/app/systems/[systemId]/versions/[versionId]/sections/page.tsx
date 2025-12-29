"use client";

import { useAuth } from "@/components/auth/auth-provider";
import { RequireAuth } from "@/components/auth/require-auth";
import { AppShell } from "@/components/layout/app-shell";
import { ApiError, apiRequest } from "@/lib/http";
import type { CompletenessResponse, SectionListResponse } from "@/lib/types";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

export default function SectionsPage() {
  const { systemId, versionId } = useParams<{ systemId: string; versionId: string }>();
  const { accessToken } = useAuth();

  const [sections, setSections] = useState<SectionListResponse | null>(null);
  const [completeness, setCompleteness] = useState<CompletenessResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const completenessByKey = useMemo(() => {
    const map = new Map<string, CompletenessResponse["sections"][number]>();
    if (!completeness) return map;
    for (const s of completeness.sections) map.set(s.section_key, s);
    return map;
  }, [completeness]);

  useEffect(() => {
    let isMounted = true;
    (async () => {
      if (!accessToken) return;
      setIsLoading(true);
      setError(null);
      try {
        const [sectionsData, completenessData] = await Promise.all([
          apiRequest<SectionListResponse>(
            `/api/systems/${systemId}/versions/${versionId}/sections`,
            {},
            { accessToken },
          ),
          apiRequest<CompletenessResponse>(
            `/api/systems/${systemId}/versions/${versionId}/completeness`,
            {},
            { accessToken },
          ),
        ]);
        if (!isMounted) return;
        setSections(sectionsData);
        setCompleteness(completenessData);
      } catch (err) {
        if (isMounted) {
          setError(err instanceof ApiError ? "Failed to load sections." : "Unexpected error.");
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    })();
    return () => {
      isMounted = false;
    };
  }, [accessToken, systemId, versionId]);

  return (
    <AppShell>
      <RequireAuth>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Sections</h1>
            <div className="mt-1 text-xs text-zinc-500">
              <Link href={`/systems/${systemId}/versions/${versionId}`} className="hover:underline">
                Version
              </Link>{" "}
              / Annex IV sections
            </div>
          </div>
          {completeness ? (
            <div className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm">
              Overall completeness:{" "}
              <span className="font-mono">{Math.round(completeness.overall_score)}%</span>
            </div>
          ) : null}
        </div>

        {isLoading ? (
          <div className="mt-6 text-sm text-zinc-600">Loading…</div>
        ) : error ? (
          <div className="mt-6 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : !sections ? (
          <div className="mt-6 text-sm text-zinc-600">Not found.</div>
        ) : (
          <div className="mt-6 grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2 rounded-xl border border-zinc-200 bg-white">
              <ul className="divide-y divide-zinc-100">
                {sections.items.map((section) => {
                  const comp = completenessByKey.get(section.section_key);
                  const score = comp ? comp.score : section.completeness_score;
                  const evidenceCount = comp ? comp.evidence_count : section.evidence_refs.length;
                  return (
                    <li key={section.id} className="p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <Link
                            href={`/systems/${systemId}/versions/${versionId}/sections/${encodeURIComponent(
                              section.section_key,
                            )}`}
                            className="text-sm font-semibold hover:underline"
                          >
                            {section.title}
                          </Link>
                          <div className="mt-1 text-xs text-zinc-500 font-mono">{section.section_key}</div>
                          <div className="mt-3 flex items-center gap-3">
                            <div className="h-2 w-40 overflow-hidden rounded-full bg-zinc-100">
                              <div
                                className="h-full bg-zinc-900"
                                style={{ width: `${Math.max(0, Math.min(100, score))}%` }}
                              />
                            </div>
                            <div className="text-xs text-zinc-600">
                              <span className="font-mono">{Math.round(score)}%</span> · evidence{" "}
                              <span className="font-mono">{evidenceCount}</span>
                            </div>
                          </div>
                        </div>
                        <div className="shrink-0 text-right text-xs text-zinc-500">
                          updated {section.updated_at}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>

            <div className="space-y-6">
              <div className="rounded-xl border border-zinc-200 bg-white p-6">
                <h2 className="text-sm font-medium">Top gaps</h2>
                <p className="mt-1 text-xs text-zinc-500">Prioritized missing fields / evidence.</p>
                {completeness && completeness.gaps.length > 0 ? (
                  <ul className="mt-4 space-y-2 text-sm">
                    {completeness.gaps.slice(0, 8).map((g, idx) => (
                      <li key={`${g.section_key}-${idx}`} className="rounded-md border border-zinc-200 bg-zinc-50 p-3">
                        <div className="text-xs text-zinc-500 font-mono">{g.section_key}</div>
                        <div className="mt-1">{g.description}</div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="mt-4 text-sm text-zinc-600">No gaps detected.</div>
                )}
              </div>
            </div>
          </div>
        )}
      </RequireAuth>
    </AppShell>
  );
}


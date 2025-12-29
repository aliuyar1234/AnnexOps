"use client";

import { useAuth } from "@/components/auth/auth-provider";
import { RequireAuth } from "@/components/auth/require-auth";
import { AppShell } from "@/components/layout/app-shell";
import { ApiError, apiRequest } from "@/lib/http";
import type { DownloadUrlResponse, EvidenceDetailResponse } from "@/lib/types";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

export default function EvidenceDetailPage() {
  const { evidenceId } = useParams<{ evidenceId: string }>();
  const { accessToken } = useAuth();

  const [evidence, setEvidence] = useState<EvidenceDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const prettyMetadata = useMemo(() => {
    if (!evidence) return "";
    try {
      return JSON.stringify(evidence.type_metadata, null, 2);
    } catch {
      return String(evidence.type_metadata);
    }
  }, [evidence]);

  useEffect(() => {
    let isMounted = true;
    (async () => {
      if (!accessToken) return;
      setIsLoading(true);
      setError(null);
      try {
        const data = await apiRequest<EvidenceDetailResponse>(
          `/api/evidence/${evidenceId}`,
          {},
          { accessToken },
        );
        if (isMounted) setEvidence(data);
      } catch (err) {
        if (isMounted) {
          setError(err instanceof ApiError ? "Failed to load evidence." : "Unexpected error.");
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    })();
    return () => {
      isMounted = false;
    };
  }, [accessToken, evidenceId]);

  async function download() {
    if (!accessToken || !evidence) return;
    try {
      const data = await apiRequest<DownloadUrlResponse>(
        `/api/evidence/${evidenceId}/download-url`,
        {},
        { accessToken },
      );
      const opened = window.open(data.download_url, "_blank", "noopener,noreferrer");
      if (!opened) window.location.assign(data.download_url);
    } catch {
      // noop
    }
  }

  return (
    <AppShell>
      <RequireAuth>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Evidence</h1>
            <div className="mt-1 text-xs text-zinc-500">
              <Link href="/evidence" className="hover:underline">
                Evidence
              </Link>{" "}
              / <span className="font-mono">{evidenceId}</span>
            </div>
          </div>
          {evidence && evidence.type === "upload" ? (
            <button
              type="button"
              onClick={() => void download()}
              className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm hover:bg-zinc-50"
            >
              Download
            </button>
          ) : null}
        </div>

        {isLoading ? (
          <div className="mt-6 text-sm text-zinc-600">Loading…</div>
        ) : error ? (
          <div className="mt-6 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : !evidence ? (
          <div className="mt-6 text-sm text-zinc-600">Not found.</div>
        ) : (
          <div className="mt-6 grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2 space-y-6">
              <div className="rounded-xl border border-zinc-200 bg-white p-6">
                <div className="text-lg font-semibold tracking-tight">{evidence.title}</div>
                <div className="mt-1 text-xs text-zinc-500">
                  {evidence.type} · {evidence.classification} · used{" "}
                  <span className="font-mono">{evidence.usage_count}</span>
                </div>
                {evidence.tags.length > 0 ? (
                  <div className="mt-3 flex flex-wrap gap-1">
                    {evidence.tags.map((t) => (
                      <span
                        key={t}
                        className="rounded-full border border-zinc-200 bg-white px-2 py-0.5 text-xs text-zinc-600"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                ) : null}
                {evidence.description ? (
                  <p className="mt-3 text-sm text-zinc-700">{evidence.description}</p>
                ) : null}
              </div>

              <div className="rounded-xl border border-zinc-200 bg-white p-6">
                <h2 className="text-sm font-medium">Type metadata</h2>
                <pre className="mt-3 overflow-auto rounded-md border border-zinc-200 bg-zinc-50 p-3 text-xs">
                  <code>{prettyMetadata}</code>
                </pre>
              </div>
            </div>

            <div className="space-y-6">
              <div className="rounded-xl border border-zinc-200 bg-white p-6">
                <h2 className="text-sm font-medium">Mapped versions</h2>
                {evidence.mapped_versions.length > 0 ? (
                  <ul className="mt-3 space-y-2 text-sm">
                    {evidence.mapped_versions.map((v) => (
                      <li key={v.id} className="rounded-md border border-zinc-200 bg-zinc-50 p-3">
                        <Link
                          href={`/systems/${v.system_id}/versions/${v.id}`}
                          className="font-semibold hover:underline"
                        >
                          {v.system_name} · {v.label}
                        </Link>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="mt-3 text-sm text-zinc-600">Not mapped yet.</div>
                )}
              </div>
            </div>
          </div>
        )}
      </RequireAuth>
    </AppShell>
  );
}


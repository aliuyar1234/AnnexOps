"use client";

import { useAuth } from "@/components/auth/auth-provider";
import { RequireAuth } from "@/components/auth/require-auth";
import { AppShell } from "@/components/layout/app-shell";
import { ApiError, apiRequest } from "@/lib/http";
import { hasAtLeast } from "@/lib/rbac";
import type {
  DownloadUrlResponse,
  ExportListResponse,
  ExportResponse,
  VersionListResponse,
  VersionResponse,
} from "@/lib/types";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState, type FormEvent } from "react";

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

export default function ExportsPage() {
  const { systemId, versionId } = useParams<{ systemId: string; versionId: string }>();
  const { accessToken, user } = useAuth();
  const canCreate = hasAtLeast(user?.role, "editor");

  const [exportsData, setExportsData] = useState<ExportListResponse | null>(null);
  const [versions, setVersions] = useState<VersionResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [includeDiff, setIncludeDiff] = useState(false);
  const [compareVersionId, setCompareVersionId] = useState<string>("");
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const compareOptions = useMemo(
    () => versions.filter((v) => v.id !== versionId),
    [versions, versionId],
  );

  async function refresh() {
    if (!accessToken) return;
    setIsLoading(true);
    setError(null);
    try {
      const [exportsList, versionList] = await Promise.all([
        apiRequest<ExportListResponse>(
          `/api/systems/${systemId}/versions/${versionId}/exports?limit=100&offset=0`,
          {},
          { accessToken },
        ),
        apiRequest<VersionListResponse>(
          `/api/systems/${systemId}/versions?limit=100&offset=0`,
          {},
          { accessToken },
        ),
      ]);
      setExportsData(exportsList);
      setVersions(versionList.items);
    } catch (err) {
      setError(err instanceof ApiError ? "Failed to load exports." : "Unexpected error.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, systemId, versionId]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setCreateError(null);

    if (!accessToken) return;
    if (!canCreate) {
      setCreateError("Editor role required to create exports.");
      return;
    }
    if (includeDiff && !compareVersionId) {
      setCreateError("Pick a compare version for diff exports.");
      return;
    }

    setIsCreating(true);
    try {
      await apiRequest<ExportResponse>(
        `/api/systems/${systemId}/versions/${versionId}/exports`,
        {
          method: "POST",
          body: JSON.stringify({
            include_diff: includeDiff,
            compare_version_id: includeDiff ? compareVersionId : null,
          }),
        },
        { accessToken },
      );
      setIncludeDiff(false);
      setCompareVersionId("");
      await refresh();
    } catch (err) {
      setCreateError(err instanceof ApiError ? "Export creation failed." : "Unexpected error.");
    } finally {
      setIsCreating(false);
    }
  }

  async function downloadExport(exportId: string) {
    if (!accessToken) return;
    try {
      const data = await apiRequest<DownloadUrlResponse>(
        `/api/exports/${exportId}/download-url`,
        {},
        { accessToken },
      );
      const opened = window.open(data.download_url, "_blank", "noopener,noreferrer");
      if (!opened) {
        window.location.assign(data.download_url);
      }
    } catch {
      // noop; user can retry
    }
  }

  return (
    <AppShell>
      <RequireAuth>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Exports</h1>
            <div className="mt-1 text-xs text-zinc-500">
              <Link href={`/systems/${systemId}/versions/${versionId}`} className="hover:underline">
                Version
              </Link>{" "}
              / exports
            </div>
          </div>
        </div>

        {isLoading ? (
          <div className="mt-6 text-sm text-zinc-600">Loading…</div>
        ) : error ? (
          <div className="mt-6 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : (
          <div className="mt-6 grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2 rounded-xl border border-zinc-200 bg-white">
              {exportsData && exportsData.items.length > 0 ? (
                <ul className="divide-y divide-zinc-100">
                  {exportsData.items.map((ex) => (
                    <li key={ex.id} className="p-4">
                      <div className="flex flex-wrap items-start justify-between gap-4">
                        <div>
                          <div className="text-sm font-semibold">Export</div>
                          <div className="mt-1 text-xs text-zinc-500">
                            hash <span className="font-mono">{ex.snapshot_hash.slice(0, 12)}…</span> ·{" "}
                            {formatBytes(ex.file_size)}
                            {ex.include_diff ? " · diff" : ""}
                          </div>
                          <div className="mt-1 text-xs text-zinc-500">
                            created <span className="font-mono">{ex.created_at}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => void downloadExport(ex.id)}
                            className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm hover:bg-zinc-50"
                          >
                            Download
                          </button>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="p-4 text-sm text-zinc-600">No exports yet.</div>
              )}
            </div>

            <div className="rounded-xl border border-zinc-200 bg-white p-6">
              <h2 className="text-sm font-medium">Create export</h2>
              <p className="mt-1 text-xs text-zinc-500">
                Requires <span className="font-mono">editor</span> or higher.
              </p>

              <form className="mt-4 space-y-3" onSubmit={onCreate}>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={includeDiff}
                    onChange={(e) => setIncludeDiff(e.target.checked)}
                    disabled={!canCreate}
                  />
                  Include diff report
                </label>

                {includeDiff ? (
                  <div>
                    <label className="text-xs font-medium">Compare against</label>
                    <select
                      value={compareVersionId}
                      onChange={(e) => setCompareVersionId(e.target.value)}
                      disabled={!canCreate}
                      className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400 disabled:bg-zinc-50"
                    >
                      <option value="">Select version</option>
                      {compareOptions.map((v) => (
                        <option key={v.id} value={v.id}>
                          {v.label} ({v.status})
                        </option>
                      ))}
                    </select>
                  </div>
                ) : null}

                {createError ? (
                  <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                    {createError}
                  </div>
                ) : null}

                <button
                  type="submit"
                  disabled={!canCreate || isCreating}
                  className="w-full rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isCreating ? "Creating…" : "Create export"}
                </button>
              </form>
            </div>
          </div>
        )}
      </RequireAuth>
    </AppShell>
  );
}


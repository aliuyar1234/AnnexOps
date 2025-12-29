"use client";

import { useAuth } from "@/components/auth/auth-provider";
import { RequireAuth } from "@/components/auth/require-auth";
import { AppShell } from "@/components/layout/app-shell";
import { ApiError, apiRequest } from "@/lib/http";
import { hasAtLeast } from "@/lib/rbac";
import type { VersionDetailResponse, VersionResponse } from "@/lib/types";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState, type FormEvent } from "react";

type Status = "draft" | "review" | "approved" | string;

export default function VersionDetailPage() {
  const { systemId, versionId } = useParams<{ systemId: string; versionId: string }>();
  const { accessToken, user } = useAuth();
  const canEdit = hasAtLeast(user?.role, "editor");
  const isAdmin = hasAtLeast(user?.role, "admin");

  const [version, setVersion] = useState<VersionDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [notes, setNotes] = useState("");
  const [releaseDate, setReleaseDate] = useState<string>("");
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [isChangingStatus, setIsChangingStatus] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    (async () => {
      if (!accessToken) return;
      setIsLoading(true);
      setError(null);
      try {
        const data = await apiRequest<VersionDetailResponse>(
          `/api/systems/${systemId}/versions/${versionId}`,
          {},
          { accessToken },
        );
        if (!isMounted) return;
        setVersion(data);
        setNotes(data.notes ?? "");
        setReleaseDate(data.release_date ?? "");
      } catch (err) {
        if (isMounted) {
          setError(err instanceof ApiError ? "Failed to load version." : "Unexpected error.");
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    })();
    return () => {
      isMounted = false;
    };
  }, [accessToken, systemId, versionId]);

  const status = (version?.status ?? "draft") as Status;

  const statusActions = useMemo(() => {
    if (!version) return [];
    if (status === "draft") {
      return [{ to: "review", label: "Send to review", allowed: canEdit }];
    }
    if (status === "review") {
      return [
        { to: "draft", label: "Back to draft", allowed: canEdit },
        { to: "approved", label: "Approve", allowed: isAdmin },
      ];
    }
    return [];
  }, [version, status, canEdit, isAdmin]);

  async function onSave(e: FormEvent) {
    e.preventDefault();
    setSaveError(null);
    if (!accessToken || !version) return;
    if (!canEdit) {
      setSaveError("Editor role required to edit versions.");
      return;
    }

    setIsSaving(true);
    try {
      const updated = await apiRequest<VersionDetailResponse>(
        `/api/systems/${systemId}/versions/${versionId}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            notes: notes.trim() ? notes.trim() : null,
            release_date: releaseDate ? releaseDate : null,
          }),
        },
        { accessToken },
      );
      setVersion(updated);
      setNotes(updated.notes ?? "");
      setReleaseDate(updated.release_date ?? "");
    } catch (err) {
      setSaveError(err instanceof ApiError ? "Update failed." : "Unexpected error.");
    } finally {
      setIsSaving(false);
    }
  }

  async function changeStatus(next: string) {
    setStatusError(null);
    if (!accessToken || !version) return;
    if (!canEdit && next !== "approved") {
      setStatusError("Editor role required for this action.");
      return;
    }
    if (next === "approved" && !isAdmin) {
      setStatusError("Admin role required to approve.");
      return;
    }

    setIsChangingStatus(true);
    try {
      const updated = await apiRequest<VersionResponse>(
        `/api/systems/${systemId}/versions/${versionId}/status`,
        { method: "PATCH", body: JSON.stringify({ status: next, comment: null }) },
        { accessToken },
      );
      setVersion((prev) => (prev ? { ...prev, ...updated } : (updated as VersionDetailResponse)));
    } catch (err) {
      setStatusError(err instanceof ApiError ? "Status change failed." : "Unexpected error.");
    } finally {
      setIsChangingStatus(false);
    }
  }

  return (
    <AppShell>
      <RequireAuth>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Version</h1>
            <div className="mt-1 text-xs text-zinc-500">
              <Link href={`/systems/${systemId}`} className="hover:underline">
                System
              </Link>{" "}
              / <span className="font-mono">{versionId}</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              href={`/systems/${systemId}/versions/${versionId}/sections`}
              className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm hover:bg-zinc-50"
            >
              Open sections
            </Link>
            <Link
              href={`/systems/${systemId}/versions/${versionId}/coverage`}
              className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm hover:bg-zinc-50"
            >
              Coverage
            </Link>
            <Link
              href={`/systems/${systemId}/versions/${versionId}/decision-logs`}
              className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm hover:bg-zinc-50"
            >
              Decision logs
            </Link>
            <Link
              href={`/systems/${systemId}/versions/${versionId}/exports`}
              className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm hover:bg-zinc-50"
            >
              Exports
            </Link>
          </div>
        </div>

        {isLoading ? (
          <div className="mt-6 text-sm text-zinc-600">Loading…</div>
        ) : error ? (
          <div className="mt-6 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : !version ? (
          <div className="mt-6 text-sm text-zinc-600">Not found.</div>
        ) : (
          <div className="mt-6 grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2 space-y-6">
              <div className="rounded-xl border border-zinc-200 bg-white p-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-lg font-semibold tracking-tight">{version.label}</div>
                    <div className="mt-1 text-xs text-zinc-500">
                      status: <span className="font-mono">{version.status}</span>
                      {version.release_date ? ` · release: ${version.release_date}` : ""}
                    </div>
                  </div>
                  <div className="text-right text-xs text-zinc-500">
                    {version.created_by ? `by ${version.created_by.email}` : "—"}
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-2">
                  {statusActions.map((a) => (
                    <button
                      key={a.to}
                      type="button"
                      disabled={!a.allowed || isChangingStatus}
                      onClick={() => void changeStatus(a.to)}
                      className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {a.label}
                    </button>
                  ))}
                  {statusError ? <div className="text-sm text-red-700">{statusError}</div> : null}
                </div>
              </div>

              <div className="rounded-xl border border-zinc-200 bg-white p-6">
                <h2 className="text-sm font-medium">Edit metadata</h2>
                <p className="mt-1 text-xs text-zinc-500">Requires editor or higher.</p>

                <form className="mt-4 space-y-3" onSubmit={onSave}>
                  <div>
                    <label className="text-xs font-medium">Release date</label>
                    <input
                      type="date"
                      value={releaseDate}
                      onChange={(e) => setReleaseDate(e.target.value)}
                      className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                      disabled={!canEdit}
                    />
                  </div>

                  <div>
                    <label className="text-xs font-medium">Notes</label>
                    <textarea
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      rows={4}
                      className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                      disabled={!canEdit}
                    />
                  </div>

                  {saveError ? (
                    <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                      {saveError}
                    </div>
                  ) : null}

                  <button
                    type="submit"
                    disabled={!canEdit || isSaving}
                    className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isSaving ? "Saving…" : "Save"}
                  </button>
                </form>
              </div>
            </div>

            <div className="space-y-6">
              <div className="rounded-xl border border-zinc-200 bg-white p-6">
                <h2 className="text-sm font-medium">At a glance</h2>
                <div className="mt-4 grid gap-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-600">Sections</span>
                    <span className="font-mono">{version.section_count}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-600">Evidence</span>
                    <span className="font-mono">{version.evidence_count}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-600">Updated</span>
                    <span className="font-mono">{version.updated_at}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </RequireAuth>
    </AppShell>
  );
}

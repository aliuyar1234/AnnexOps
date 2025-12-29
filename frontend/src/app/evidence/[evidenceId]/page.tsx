"use client";

import { useAuth } from "@/components/auth/auth-provider";
import { RequireAuth } from "@/components/auth/require-auth";
import { AppShell } from "@/components/layout/app-shell";
import { ApiError, apiRequest } from "@/lib/http";
import { hasAtLeast } from "@/lib/rbac";
import type { DownloadUrlResponse, EvidenceDetailResponse } from "@/lib/types";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState, type FormEvent } from "react";

export default function EvidenceDetailPage() {
  const { evidenceId } = useParams<{ evidenceId: string }>();
  const { accessToken, user } = useAuth();
  const canEdit = hasAtLeast(user?.role, "editor");

  const [evidence, setEvidence] = useState<EvidenceDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [tagsInput, setTagsInput] = useState("");
  const [classification, setClassification] = useState("internal");
  const [typeMetadataDraft, setTypeMetadataDraft] = useState("");
  const [typeMetadataError, setTypeMetadataError] = useState<string | null>(null);

  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);

  const canEditTypeMetadata = canEdit && evidence?.type !== "upload";

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
        if (!isMounted) return;
        setEvidence(data);
        setTitle(data.title ?? "");
        setDescription(data.description ?? "");
        setTagsInput((data.tags ?? []).join(", "));
        setClassification(data.classification ?? "internal");
        setTypeMetadataDraft(JSON.stringify(data.type_metadata ?? {}, null, 2));
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

  function parseTags(raw: string): string[] {
    const parts = raw
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    return Array.from(new Set(parts));
  }

  async function onSave(e: FormEvent) {
    e.preventDefault();
    setSaveError(null);
    setSaveSuccess(null);
    setTypeMetadataError(null);
    if (!accessToken || !evidence) return;
    if (!canEdit) {
      setSaveError("Editor role required to edit evidence.");
      return;
    }

    const nextTitle = title.trim();
    if (!nextTitle) {
      setSaveError("Title is required.");
      return;
    }

    const payload: Record<string, unknown> = {
      title: nextTitle,
      description: description.trim() ? description.trim() : null,
      tags: parseTags(tagsInput),
      classification,
    };

    if (canEditTypeMetadata) {
      try {
        const parsed = JSON.parse(typeMetadataDraft || "{}") as unknown;
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
          setTypeMetadataError("Type metadata must be a JSON object.");
          return;
        }
        payload.type_metadata = parsed;
      } catch {
        setTypeMetadataError("Invalid JSON.");
        return;
      }
    }

    setIsSaving(true);
    try {
      const updated = await apiRequest<EvidenceDetailResponse>(
        `/api/evidence/${evidenceId}`,
        { method: "PATCH", body: JSON.stringify(payload) },
        { accessToken },
      );
      setEvidence(updated);
      setTitle(updated.title ?? "");
      setDescription(updated.description ?? "");
      setTagsInput((updated.tags ?? []).join(", "));
      setClassification(updated.classification ?? "internal");
      setTypeMetadataDraft(JSON.stringify(updated.type_metadata ?? {}, null, 2));
      setSaveSuccess("Saved.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        setSaveError("Validation failed. Please check your inputs.");
      } else {
        setSaveError(err instanceof ApiError ? "Update failed." : "Unexpected error.");
      }
    } finally {
      setIsSaving(false);
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
                <h2 className="text-sm font-medium">Edit metadata</h2>
                <p className="mt-1 text-xs text-zinc-500">Requires editor or higher.</p>

                <form className="mt-4 space-y-3" onSubmit={onSave}>
                  <div>
                    <label className="text-xs font-medium">Title</label>
                    <input
                      value={title}
                      onChange={(ev) => setTitle(ev.target.value)}
                      className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                      disabled={!canEdit}
                    />
                  </div>

                  <div>
                    <label className="text-xs font-medium">Description</label>
                    <textarea
                      value={description}
                      onChange={(ev) => setDescription(ev.target.value)}
                      rows={4}
                      className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                      disabled={!canEdit}
                    />
                  </div>

                  <div>
                    <label className="text-xs font-medium">Tags</label>
                    <input
                      value={tagsInput}
                      onChange={(ev) => setTagsInput(ev.target.value)}
                      placeholder="comma,separated,tags"
                      className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                      disabled={!canEdit}
                    />
                  </div>

                  <div>
                    <label className="text-xs font-medium">Classification</label>
                    <select
                      value={classification}
                      onChange={(ev) => setClassification(ev.target.value)}
                      className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                      disabled={!canEdit}
                    >
                      <option value="public">public</option>
                      <option value="internal">internal</option>
                      <option value="confidential">confidential</option>
                    </select>
                  </div>

                  {canEditTypeMetadata ? (
                    <div>
                      <label className="text-xs font-medium">Type metadata (JSON)</label>
                      <textarea
                        value={typeMetadataDraft}
                        onChange={(ev) => setTypeMetadataDraft(ev.target.value)}
                        rows={8}
                        className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 font-mono text-xs outline-none focus:border-zinc-400"
                        disabled={!canEdit}
                      />
                      {typeMetadataError ? (
                        <div className="mt-2 text-xs text-red-700">{typeMetadataError}</div>
                      ) : null}
                    </div>
                  ) : (
                    <div className="text-xs text-zinc-500">
                      Type metadata editing is disabled for upload evidence.
                    </div>
                  )}

                  {saveError ? (
                    <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                      {saveError}
                    </div>
                  ) : null}
                  {saveSuccess ? (
                    <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                      {saveSuccess}
                    </div>
                  ) : null}

                  <button
                    type="submit"
                    disabled={!canEdit || isSaving}
                    className="w-full rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isSaving ? "Saving…" : "Save changes"}
                  </button>
                </form>
              </div>

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


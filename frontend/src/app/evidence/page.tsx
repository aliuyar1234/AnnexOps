"use client";

import { useAuth } from "@/components/auth/auth-provider";
import { RequireAuth } from "@/components/auth/require-auth";
import { AppShell } from "@/components/layout/app-shell";
import { CLASSIFICATIONS, EVIDENCE_TYPES } from "@/lib/enums";
import { ApiError, apiRequest } from "@/lib/http";
import { hasAtLeast } from "@/lib/rbac";
import type { EvidenceListResponse, EvidenceResponse } from "@/lib/types";
import Link from "next/link";
import { useEffect, useMemo, useState, type FormEvent } from "react";

type EvidenceType = (typeof EVIDENCE_TYPES)[number]["value"];
type Classification = (typeof CLASSIFICATIONS)[number]["value"];

function parseTags(raw: string): string[] {
  return raw
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean)
    .slice(0, 20);
}

async function sha256Hex(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest("SHA-256", buffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}

export default function EvidencePage() {
  const { accessToken, user } = useAuth();
  const canCreate = hasAtLeast(user?.role, "editor");

  const [items, setItems] = useState<EvidenceResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [limit] = useState(20);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [classificationFilter, setClassificationFilter] = useState<string>("");
  const [orphanedFilter, setOrphanedFilter] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [createType, setCreateType] = useState<EvidenceType>("upload");
  const [createTitle, setCreateTitle] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [createTags, setCreateTags] = useState("");
  const [createClassification, setCreateClassification] =
    useState<Classification>("internal");

  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [urlValue, setUrlValue] = useState("");
  const [urlAccessedAt, setUrlAccessedAt] = useState("");

  const [gitRepoUrl, setGitRepoUrl] = useState("");
  const [gitCommitHash, setGitCommitHash] = useState("");
  const [gitBranch, setGitBranch] = useState("");
  const [gitFilePath, setGitFilePath] = useState("");

  const [ticketId, setTicketId] = useState("");
  const [ticketSystem, setTicketSystem] = useState("");
  const [ticketUrl, setTicketUrl] = useState("");

  const [noteContent, setNoteContent] = useState("");

  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createSuccess, setCreateSuccess] = useState<string | null>(null);

  const canPrev = offset > 0;
  const canNext = offset + limit < total;

  const filteredItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter((e) => {
      const haystack = `${e.title} ${e.description ?? ""}`.toLowerCase();
      return haystack.includes(q);
    });
  }, [items, search]);

  async function refreshList() {
    if (!accessToken) return;
    setIsLoading(true);
    setError(null);

    const params = new URLSearchParams();
    params.set("limit", String(limit));
    params.set("offset", String(offset));
    if (search.trim()) params.set("search", search.trim());
    if (typeFilter) params.set("type", typeFilter);
    if (classificationFilter) params.set("classification", classificationFilter);
    if (orphanedFilter === "true" || orphanedFilter === "false")
      params.set("orphaned", orphanedFilter);

    try {
      const data = await apiRequest<EvidenceListResponse>(
        `/api/evidence?${params.toString()}`,
        {},
        { accessToken },
      );
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof ApiError ? "Failed to load evidence." : "Unexpected error.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void refreshList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, limit, offset, search, typeFilter, classificationFilter, orphanedFilter]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setCreateError(null);
    setCreateSuccess(null);

    if (!accessToken) return;
    if (!canCreate) {
      setCreateError("Editor role required to create evidence.");
      return;
    }

    setIsCreating(true);
    try {
      const tags = parseTags(createTags);
      const base = {
        type: createType,
        title: createTitle.trim(),
        description: createDescription.trim() ? createDescription.trim() : null,
        tags,
        classification: createClassification,
      };

      if (createType === "upload") {
        if (!uploadFile) {
          setCreateError("Choose a file to upload.");
          return;
        }
        const filename = uploadFile.name;
        const mimeType = uploadFile.type || "application/octet-stream";
        const fileSize = uploadFile.size;
        const checksum = await sha256Hex(uploadFile);

        const uploadInfo = await apiRequest<{
          upload_url: string;
          storage_uri: string;
          expires_in: number;
        }>(
          "/api/evidence/upload-url",
          {
            method: "POST",
            body: JSON.stringify({ filename, mime_type: mimeType }),
          },
          { accessToken },
        );

        const putRes = await fetch(uploadInfo.upload_url, {
          method: "PUT",
          body: uploadFile,
          headers: { "Content-Type": mimeType },
        });
        if (!putRes.ok) {
          throw new Error(`Upload failed (${putRes.status})`);
        }

        await apiRequest<EvidenceResponse>(
          "/api/evidence",
          {
            method: "POST",
            body: JSON.stringify({
              ...base,
              type_metadata: {
                storage_uri: uploadInfo.storage_uri,
                checksum_sha256: checksum,
                file_size: fileSize,
                mime_type: mimeType,
                original_filename: filename,
              },
            }),
          },
          { accessToken },
        );
      } else if (createType === "url") {
        await apiRequest<EvidenceResponse>(
          "/api/evidence",
          {
            method: "POST",
            body: JSON.stringify({
              ...base,
              type_metadata: {
                url: urlValue.trim(),
                accessed_at: urlAccessedAt ? new Date(urlAccessedAt).toISOString() : null,
              },
            }),
          },
          { accessToken },
        );
      } else if (createType === "git") {
        await apiRequest<EvidenceResponse>(
          "/api/evidence",
          {
            method: "POST",
            body: JSON.stringify({
              ...base,
              type_metadata: {
                repo_url: gitRepoUrl.trim(),
                commit_hash: gitCommitHash.trim(),
                branch: gitBranch.trim() || null,
                file_path: gitFilePath.trim() || null,
              },
            }),
          },
          { accessToken },
        );
      } else if (createType === "ticket") {
        await apiRequest<EvidenceResponse>(
          "/api/evidence",
          {
            method: "POST",
            body: JSON.stringify({
              ...base,
              type_metadata: {
                ticket_id: ticketId.trim(),
                ticket_system: ticketSystem.trim(),
                ticket_url: ticketUrl.trim() || null,
              },
            }),
          },
          { accessToken },
        );
      } else if (createType === "note") {
        await apiRequest<EvidenceResponse>(
          "/api/evidence",
          {
            method: "POST",
            body: JSON.stringify({
              ...base,
              type_metadata: {
                content: noteContent,
              },
            }),
          },
          { accessToken },
        );
      }

      setCreateTitle("");
      setCreateDescription("");
      setCreateTags("");
      setCreateClassification("internal");
      setUploadFile(null);
      setUrlValue("");
      setUrlAccessedAt("");
      setGitRepoUrl("");
      setGitCommitHash("");
      setGitBranch("");
      setGitFilePath("");
      setTicketId("");
      setTicketSystem("");
      setTicketUrl("");
      setNoteContent("");

      setCreateSuccess("Evidence created.");
      setOffset(0);
      await refreshList();
    } catch (err) {
      setCreateError(err instanceof ApiError ? "Create failed." : (err instanceof Error ? err.message : "Unexpected error."));
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <AppShell>
      <RequireAuth>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Evidence</h1>
            <p className="mt-2 text-sm text-zinc-600">Upload or reference artifacts and map them to sections.</p>
          </div>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <div className="flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <input
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value);
                    setOffset(0);
                  }}
                  placeholder="Search (title/description)"
                  className="w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400 sm:w-64"
                />
                <select
                  value={typeFilter}
                  onChange={(e) => {
                    setTypeFilter(e.target.value);
                    setOffset(0);
                  }}
                  className="w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400 sm:w-48"
                >
                  <option value="">All types</option>
                  {EVIDENCE_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
                <select
                  value={classificationFilter}
                  onChange={(e) => {
                    setClassificationFilter(e.target.value);
                    setOffset(0);
                  }}
                  className="w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400 sm:w-48"
                >
                  <option value="">All classifications</option>
                  {CLASSIFICATIONS.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
                <select
                  value={orphanedFilter}
                  onChange={(e) => {
                    setOrphanedFilter(e.target.value);
                    setOffset(0);
                  }}
                  className="w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400 sm:w-48"
                >
                  <option value="">All</option>
                  <option value="true">Orphaned</option>
                  <option value="false">Mapped</option>
                </select>
              </div>

              <div className="flex items-center justify-between gap-2 sm:justify-end">
                <div className="text-xs text-zinc-500">
                  {total} total · page {Math.floor(offset / limit) + 1}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={!canPrev}
                    onClick={() => setOffset((o) => Math.max(0, o - limit))}
                    className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Prev
                  </button>
                  <button
                    type="button"
                    disabled={!canNext}
                    onClick={() => setOffset((o) => o + limit)}
                    className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Next
                  </button>
                </div>
              </div>
            </div>

            <div className="mt-4 rounded-xl border border-zinc-200 bg-white">
              {isLoading ? (
                <div className="p-4 text-sm text-zinc-600">Loading…</div>
              ) : error ? (
                <div className="p-4 text-sm text-red-700">{error}</div>
              ) : filteredItems.length === 0 ? (
                <div className="p-4 text-sm text-zinc-600">No evidence found.</div>
              ) : (
                <ul className="divide-y divide-zinc-100">
                  {filteredItems.map((ev) => (
                    <li key={ev.id} className="p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <Link href={`/evidence/${ev.id}`} className="text-sm font-semibold hover:underline">
                            {ev.title}
                          </Link>
                          <div className="mt-1 text-xs text-zinc-500">
                            {ev.type} · {ev.classification} ·{" "}
                            {ev.usage_count !== null && ev.usage_count !== undefined ? `used ${ev.usage_count}` : "—"}
                          </div>
                          {ev.tags.length > 0 ? (
                            <div className="mt-2 flex flex-wrap gap-1">
                              {ev.tags.slice(0, 8).map((t) => (
                                <span
                                  key={t}
                                  className="rounded-full border border-zinc-200 bg-white px-2 py-0.5 text-xs text-zinc-600"
                                >
                                  {t}
                                </span>
                              ))}
                            </div>
                          ) : null}
                          {ev.duplicate_of ? (
                            <div className="mt-2 text-xs text-amber-700">
                              Duplicate of <span className="font-mono">{ev.duplicate_of}</span>
                            </div>
                          ) : null}
                          {ev.description ? (
                            <p className="mt-2 text-sm text-zinc-700">{ev.description}</p>
                          ) : null}
                        </div>
                        <div className="text-right text-xs text-zinc-500 font-mono">{ev.id.slice(0, 8)}…</div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <div className="lg:col-span-2">
            <div className="rounded-xl border border-zinc-200 bg-white p-4">
              <h2 className="text-sm font-medium">Create evidence</h2>
              <p className="mt-1 text-xs text-zinc-500">
                Requires <span className="font-mono">editor</span> or higher.
              </p>

              {!canCreate ? (
                <div className="mt-3 rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-600">
                  You don’t have permission to create evidence.
                </div>
              ) : (
                <form className="mt-4 space-y-3" onSubmit={onCreate}>
                  <div>
                    <label className="text-xs font-medium">Type</label>
                    <select
                      value={createType}
                      onChange={(e) => setCreateType(e.target.value as EvidenceType)}
                      className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                    >
                      {EVIDENCE_TYPES.map((t) => (
                        <option key={t.value} value={t.value}>
                          {t.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="text-xs font-medium">Title</label>
                    <input
                      value={createTitle}
                      onChange={(e) => setCreateTitle(e.target.value)}
                      required
                      className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-medium">Description</label>
                    <textarea
                      value={createDescription}
                      onChange={(e) => setCreateDescription(e.target.value)}
                      rows={3}
                      className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                    />
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <div>
                      <label className="text-xs font-medium">Classification</label>
                      <select
                        value={createClassification}
                        onChange={(e) => setCreateClassification(e.target.value as Classification)}
                        className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                      >
                        {CLASSIFICATIONS.map((c) => (
                          <option key={c.value} value={c.value}>
                            {c.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="text-xs font-medium">Tags</label>
                      <input
                        value={createTags}
                        onChange={(e) => setCreateTags(e.target.value)}
                        className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                        placeholder="comma,separated,tags"
                      />
                    </div>
                  </div>

                  {createType === "upload" ? (
                    <div>
                      <label className="text-xs font-medium">File</label>
                      <input
                        type="file"
                        onChange={(e) => setUploadFile(e.target.files?.item(0) ?? null)}
                        className="mt-1 w-full text-sm"
                      />
                      <p className="mt-1 text-xs text-zinc-500">
                        Client computes SHA‑256 and uploads via presigned URL.
                      </p>
                    </div>
                  ) : null}

                  {createType === "url" ? (
                    <div className="space-y-3">
                      <div>
                        <label className="text-xs font-medium">URL</label>
                        <input
                          value={urlValue}
                          onChange={(e) => setUrlValue(e.target.value)}
                          required
                          className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                          placeholder="https://…"
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium">Accessed at (optional)</label>
                        <input
                          type="datetime-local"
                          value={urlAccessedAt}
                          onChange={(e) => setUrlAccessedAt(e.target.value)}
                          className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                        />
                      </div>
                    </div>
                  ) : null}

                  {createType === "git" ? (
                    <div className="space-y-3">
                      <div>
                        <label className="text-xs font-medium">Repo URL</label>
                        <input
                          value={gitRepoUrl}
                          onChange={(e) => setGitRepoUrl(e.target.value)}
                          required
                          className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium">Commit hash (40 hex)</label>
                        <input
                          value={gitCommitHash}
                          onChange={(e) => setGitCommitHash(e.target.value)}
                          required
                          className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 font-mono text-xs outline-none focus:border-zinc-400"
                        />
                      </div>
                      <div className="grid gap-3 sm:grid-cols-2">
                        <div>
                          <label className="text-xs font-medium">Branch (optional)</label>
                          <input
                            value={gitBranch}
                            onChange={(e) => setGitBranch(e.target.value)}
                            className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                          />
                        </div>
                        <div>
                          <label className="text-xs font-medium">File path (optional)</label>
                          <input
                            value={gitFilePath}
                            onChange={(e) => setGitFilePath(e.target.value)}
                            className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                          />
                        </div>
                      </div>
                    </div>
                  ) : null}

                  {createType === "ticket" ? (
                    <div className="space-y-3">
                      <div>
                        <label className="text-xs font-medium">Ticket ID</label>
                        <input
                          value={ticketId}
                          onChange={(e) => setTicketId(e.target.value)}
                          required
                          className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium">Ticket system</label>
                        <input
                          value={ticketSystem}
                          onChange={(e) => setTicketSystem(e.target.value)}
                          required
                          className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                          placeholder="jira, github, linear…"
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium">Ticket URL (optional)</label>
                        <input
                          value={ticketUrl}
                          onChange={(e) => setTicketUrl(e.target.value)}
                          className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                          placeholder="https://…"
                        />
                      </div>
                    </div>
                  ) : null}

                  {createType === "note" ? (
                    <div>
                      <label className="text-xs font-medium">Note content (Markdown)</label>
                      <textarea
                        value={noteContent}
                        onChange={(e) => setNoteContent(e.target.value)}
                        required
                        rows={6}
                        className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                      />
                    </div>
                  ) : null}

                  {createError ? (
                    <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                      {createError}
                    </div>
                  ) : null}
                  {createSuccess ? (
                    <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                      {createSuccess}
                    </div>
                  ) : null}

                  <button
                    type="submit"
                    disabled={isCreating}
                    className="w-full rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isCreating ? "Creating…" : "Create evidence"}
                  </button>
                </form>
              )}
            </div>
          </div>
        </div>
      </RequireAuth>
    </AppShell>
  );
}


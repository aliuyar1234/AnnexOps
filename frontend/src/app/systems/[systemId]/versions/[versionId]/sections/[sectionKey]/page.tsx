"use client";

import { useAuth } from "@/components/auth/auth-provider";
import { RequireAuth } from "@/components/auth/require-auth";
import { AppShell } from "@/components/layout/app-shell";
import { ApiError, apiRequest } from "@/lib/http";
import { hasAtLeast } from "@/lib/rbac";
import type {
  CompletenessResponse,
  EvidenceListResponse,
  EvidenceResponse,
  MappingWithEvidence,
  SectionResponse,
} from "@/lib/types";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState, type FormEvent } from "react";

type EditorMode = "form" | "json";
type MappingStrength = "" | "weak" | "medium" | "strong";

function valueToEditorString(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.map(String).join("\n");
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

function parseEditorValue(input: string): unknown {
  const trimmed = input.trimEnd();
  if (!trimmed) return "";
  const lines = trimmed
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
  if (lines.length >= 2) return lines;
  return trimmed.trim();
}

export default function SectionEditorPage() {
  const { systemId, versionId, sectionKey: rawSectionKey } = useParams<{
    systemId: string;
    versionId: string;
    sectionKey: string;
  }>();

  const sectionKey = useMemo(() => decodeURIComponent(rawSectionKey), [rawSectionKey]);

  const { accessToken, user } = useAuth();
  const canEdit = hasAtLeast(user?.role, "editor");

  const [mode, setMode] = useState<EditorMode>("form");
  const [section, setSection] = useState<SectionResponse | null>(null);
  const [requiredFields, setRequiredFields] = useState<string[]>([]);
  const [contentDraft, setContentDraft] = useState<Record<string, unknown>>({});
  const [jsonDraft, setJsonDraft] = useState("");
  const [jsonError, setJsonError] = useState<string | null>(null);

  const [mappings, setMappings] = useState<MappingWithEvidence[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);

  const evidenceRefs = useMemo(() => mappings.map((m) => m.evidence_id), [mappings]);

  const [evidenceQuery, setEvidenceQuery] = useState("");
  const [evidenceResults, setEvidenceResults] = useState<EvidenceResponse[]>([]);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState("");
  const [mappingStrength, setMappingStrength] = useState<MappingStrength>("medium");
  const [mappingNotes, setMappingNotes] = useState("");
  const [isAddingMapping, setIsAddingMapping] = useState(false);
  const [mappingError, setMappingError] = useState<string | null>(null);

  async function refreshAll() {
    if (!accessToken) return;
    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      params.set("target_type", "section");
      params.set("target_key", sectionKey);
      params.set("limit", "100");
      params.set("offset", "0");

      const [sectionData, completenessData, mappingData] = await Promise.all([
        apiRequest<SectionResponse>(
          `/api/systems/${systemId}/versions/${versionId}/sections/${encodeURIComponent(sectionKey)}`,
          {},
          { accessToken },
        ),
        apiRequest<CompletenessResponse>(
          `/api/systems/${systemId}/versions/${versionId}/completeness`,
          {},
          { accessToken },
        ),
        apiRequest<MappingWithEvidence[]>(
          `/api/systems/${systemId}/versions/${versionId}/evidence?${params.toString()}`,
          {},
          { accessToken },
        ),
      ]);

      setSection(sectionData);
      setMappings(mappingData);

      const sectionInfo = completenessData.sections.find((s) => s.section_key === sectionKey);
      const fields = sectionInfo ? Object.keys(sectionInfo.field_completion) : [];
      fields.sort((a, b) => a.localeCompare(b));
      setRequiredFields(fields);

      setContentDraft(sectionData.content ?? {});
      setJsonDraft(JSON.stringify(sectionData.content ?? {}, null, 2));
      setJsonError(null);
    } catch (err) {
      setError(err instanceof ApiError ? "Failed to load section." : "Unexpected error.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void refreshAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, systemId, versionId, sectionKey]);

  useEffect(() => {
    let isMounted = true;
    (async () => {
      if (!accessToken) return;
      const query = evidenceQuery.trim();
      if (query.length < 2) {
        if (isMounted) setEvidenceResults([]);
        return;
      }

      const params = new URLSearchParams();
      params.set("search", query);
      params.set("limit", "10");
      params.set("offset", "0");

      try {
        const data = await apiRequest<EvidenceListResponse>(
          `/api/evidence?${params.toString()}`,
          {},
          { accessToken },
        );
        if (isMounted) setEvidenceResults(data.items);
      } catch {
        if (isMounted) setEvidenceResults([]);
      }
    })();

    return () => {
      isMounted = false;
    };
  }, [accessToken, evidenceQuery]);

  function updateField(field: string, rawValue: string) {
    setContentDraft((prev) => ({ ...prev, [field]: parseEditorValue(rawValue) }));
  }

  async function onSave(e: FormEvent) {
    e.preventDefault();
    setSaveError(null);
    setSaveSuccess(null);
    setJsonError(null);

    if (!accessToken || !section) return;
    if (!canEdit) {
      setSaveError("Editor role required to edit sections.");
      return;
    }

    let contentToSave: Record<string, unknown> = contentDraft;
    if (mode === "json") {
      try {
        const parsed = JSON.parse(jsonDraft);
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
          setJsonError("JSON must be an object.");
          return;
        }
        contentToSave = parsed as Record<string, unknown>;
      } catch {
        setJsonError("Invalid JSON.");
        return;
      }
    }

    setIsSaving(true);
    try {
      const updated = await apiRequest<SectionResponse>(
        `/api/systems/${systemId}/versions/${versionId}/sections/${encodeURIComponent(sectionKey)}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            content: contentToSave,
            evidence_refs: evidenceRefs,
          }),
        },
        { accessToken },
      );
      setSection(updated);
      setContentDraft(updated.content ?? {});
      setJsonDraft(JSON.stringify(updated.content ?? {}, null, 2));
      setSaveSuccess("Saved.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setSaveError("This version is immutable (approved with exports).");
      } else {
        setSaveError(err instanceof ApiError ? "Save failed." : "Unexpected error.");
      }
    } finally {
      setIsSaving(false);
    }
  }

  async function onAddMapping(e: FormEvent) {
    e.preventDefault();
    setMappingError(null);
    if (!accessToken) return;
    if (!canEdit) {
      setMappingError("Editor role required to manage mappings.");
      return;
    }

    const evidenceId = selectedEvidenceId.trim();
    if (!evidenceId) {
      setMappingError("Select an evidence item.");
      return;
    }

    setIsAddingMapping(true);
    try {
      await apiRequest(
        `/api/systems/${systemId}/versions/${versionId}/evidence`,
        {
          method: "POST",
          body: JSON.stringify({
            evidence_id: evidenceId,
            target_type: "section",
            target_key: sectionKey,
            strength: mappingStrength || null,
            notes: mappingNotes.trim() || null,
          }),
        },
        { accessToken },
      );
      setSelectedEvidenceId("");
      setEvidenceQuery("");
      setEvidenceResults([]);
      setMappingStrength("medium");
      setMappingNotes("");
      await refreshAll();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setMappingError("Mapping already exists.");
      } else {
        setMappingError(err instanceof ApiError ? "Failed to create mapping." : "Unexpected error.");
      }
    } finally {
      setIsAddingMapping(false);
    }
  }

  async function onDeleteMapping(mappingId: string) {
    setMappingError(null);
    if (!accessToken) return;
    if (!canEdit) {
      setMappingError("Editor role required to manage mappings.");
      return;
    }

    try {
      await apiRequest(
        `/api/systems/${systemId}/versions/${versionId}/evidence/${mappingId}`,
        { method: "DELETE" },
        { accessToken },
      );
      await refreshAll();
    } catch (err) {
      setMappingError(err instanceof ApiError ? "Failed to delete mapping." : "Unexpected error.");
    }
  }

  return (
    <AppShell>
      <RequireAuth>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">{section?.title ?? "Section"}</h1>
            <div className="mt-1 text-xs text-zinc-500">
              <Link href={`/systems/${systemId}/versions/${versionId}/sections`} className="hover:underline">
                Sections
              </Link>{" "}
              / <span className="font-mono">{sectionKey}</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setMode("form")}
              className={`rounded-md border px-3 py-2 text-sm ${
                mode === "form"
                  ? "border-zinc-900 bg-zinc-900 text-white"
                  : "border-zinc-200 bg-white hover:bg-zinc-50"
              }`}
            >
              Form
            </button>
            <button
              type="button"
              onClick={() => setMode("json")}
              className={`rounded-md border px-3 py-2 text-sm ${
                mode === "json"
                  ? "border-zinc-900 bg-zinc-900 text-white"
                  : "border-zinc-200 bg-white hover:bg-zinc-50"
              }`}
            >
              JSON
            </button>
          </div>
        </div>

        {isLoading ? (
          <div className="mt-6 text-sm text-zinc-600">Loading…</div>
        ) : error ? (
          <div className="mt-6 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : !section ? (
          <div className="mt-6 text-sm text-zinc-600">Not found.</div>
        ) : (
          <div className="mt-6 grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2 space-y-6">
              <div className="rounded-xl border border-zinc-200 bg-white p-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-xs text-zinc-500 font-mono">{section.section_key}</div>
                    <div className="mt-2 text-sm text-zinc-600">
                      Completeness:{" "}
                      <span className="font-mono">{Math.round(section.completeness_score)}%</span>
                    </div>
                  </div>
                  <div className="text-right text-xs text-zinc-500">
                    evidence <span className="font-mono">{evidenceRefs.length}</span>
                  </div>
                </div>

                <form className="mt-6 space-y-4" onSubmit={onSave}>
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

                  {mode === "form" ? (
                    <div className="space-y-4">
                      {requiredFields.length === 0 ? (
                        <div className="text-sm text-zinc-600">
                          No schema available for this section yet.
                        </div>
                      ) : (
                        requiredFields.map((field) => (
                          <div key={field}>
                            <label className="text-xs font-medium">{field}</label>
                            <textarea
                              value={valueToEditorString(contentDraft[field])}
                              onChange={(e) => updateField(field, e.target.value)}
                              rows={3}
                              disabled={!canEdit}
                              className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400 disabled:bg-zinc-50"
                            />
                          </div>
                        ))
                      )}
                    </div>
                  ) : (
                    <div>
                      <label className="text-xs font-medium">Content JSON</label>
                      <textarea
                        value={jsonDraft}
                        onChange={(e) => setJsonDraft(e.target.value)}
                        rows={18}
                        disabled={!canEdit}
                        className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 font-mono text-xs outline-none focus:border-zinc-400 disabled:bg-zinc-50"
                      />
                      {jsonError ? <div className="mt-2 text-sm text-red-700">{jsonError}</div> : null}
                    </div>
                  )}

                  <button
                    type="submit"
                    disabled={!canEdit || isSaving}
                    className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isSaving ? "Saving…" : "Save section"}
                  </button>
                </form>
              </div>
            </div>

            <div className="space-y-6">
              <div className="rounded-xl border border-zinc-200 bg-white p-6">
                <h2 className="text-sm font-medium">Evidence mappings</h2>
                <p className="mt-1 text-xs text-zinc-500">
                  Export evidence index is derived from mappings.
                </p>

                {mappingError ? (
                  <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                    {mappingError}
                  </div>
                ) : null}

                {mappings.length === 0 ? (
                  <div className="mt-4 text-sm text-zinc-600">No mappings yet.</div>
                ) : (
                  <ul className="mt-4 space-y-2">
                    {mappings.map((m) => (
                      <li key={m.id} className="rounded-md border border-zinc-200 bg-zinc-50 p-3">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="text-xs text-zinc-500">
                              <span className="font-mono">{m.evidence_id.slice(0, 8)}…</span>{" "}
                              · {m.evidence.type}
                              {m.strength ? ` · ${m.strength}` : ""}
                            </div>
                            <div className="mt-1 truncate text-sm font-medium">{m.evidence.title}</div>
                            {m.notes ? <div className="mt-1 text-xs text-zinc-600">{m.notes}</div> : null}
                          </div>
                          {canEdit ? (
                            <button
                              type="button"
                              onClick={() => void onDeleteMapping(m.id)}
                              className="rounded-md border border-zinc-200 bg-white px-2 py-1 text-xs hover:bg-zinc-50"
                            >
                              Remove
                            </button>
                          ) : null}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}

                <form className="mt-6 space-y-3" onSubmit={onAddMapping}>
                  <h3 className="text-sm font-medium">Add mapping</h3>
                  <div>
                    <label className="text-xs font-medium">Search evidence</label>
                    <input
                      value={evidenceQuery}
                      onChange={(e) => setEvidenceQuery(e.target.value)}
                      disabled={!canEdit}
                      className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400 disabled:bg-zinc-50"
                      placeholder="type at least 2 characters…"
                    />
                    {evidenceResults.length > 0 ? (
                      <div className="mt-2 max-h-48 overflow-auto rounded-md border border-zinc-200 bg-white">
                        {evidenceResults.map((ev) => (
                          <button
                            key={ev.id}
                            type="button"
                            onClick={() => setSelectedEvidenceId(ev.id)}
                            className={`block w-full px-3 py-2 text-left text-sm hover:bg-zinc-50 ${
                              selectedEvidenceId === ev.id ? "bg-zinc-100" : ""
                            }`}
                          >
                            <div className="truncate font-medium">{ev.title}</div>
                            <div className="mt-1 text-xs text-zinc-500 font-mono">{ev.id}</div>
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </div>

                  <div>
                    <label className="text-xs font-medium">Selected evidence ID</label>
                    <input
                      value={selectedEvidenceId}
                      onChange={(e) => setSelectedEvidenceId(e.target.value)}
                      disabled={!canEdit}
                      className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 font-mono text-xs outline-none focus:border-zinc-400 disabled:bg-zinc-50"
                      placeholder="uuid…"
                    />
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <div>
                      <label className="text-xs font-medium">Strength</label>
                      <select
                        value={mappingStrength}
                        onChange={(e) => setMappingStrength(e.target.value as MappingStrength)}
                        disabled={!canEdit}
                        className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400 disabled:bg-zinc-50"
                      >
                        <option value="">(none)</option>
                        <option value="weak">weak</option>
                        <option value="medium">medium</option>
                        <option value="strong">strong</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs font-medium">Notes</label>
                      <input
                        value={mappingNotes}
                        onChange={(e) => setMappingNotes(e.target.value)}
                        disabled={!canEdit}
                        className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400 disabled:bg-zinc-50"
                        placeholder="why this evidence supports the section…"
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={!canEdit || isAddingMapping}
                    className="w-full rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isAddingMapping ? "Adding…" : "Add mapping"}
                  </button>
                </form>
              </div>
            </div>
          </div>
        )}
      </RequireAuth>
    </AppShell>
  );
}


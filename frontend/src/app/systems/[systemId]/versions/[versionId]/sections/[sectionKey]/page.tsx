"use client";

import { useAuth } from "@/components/auth/auth-provider";
import { RequireAuth } from "@/components/auth/require-auth";
import { AppShell } from "@/components/layout/app-shell";
import { ApiError, apiRequest } from "@/lib/http";
import { hasAtLeast } from "@/lib/rbac";
import type {
  CompletenessResponse,
  DraftResponse,
  EvidenceListResponse,
  EvidenceResponse,
  GapSuggestionResponse,
  MappingWithEvidence,
  SectionResponse,
} from "@/lib/types";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState, type FormEvent } from "react";

type EditorMode = "form" | "json";
type MappingStrength = "" | "weak" | "medium" | "strong";

const CITATION_RE = /\[Evidence:\s*[0-9a-fA-F-]{36}\]/;

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

function getCitedOnlyLines(text: string): string[] {
  const rawLines = text.split("\n");
  const blocks: { lines: string[]; hasCitation: boolean; isHeading: boolean }[] = [];

  let current: string[] = [];
  let hasCitation = false;
  let isHeading = true;

  function pushBlock() {
    if (current.length === 0) return;
    blocks.push({ lines: current, hasCitation, isHeading });
    current = [];
    hasCitation = false;
    isHeading = true;
  }

  for (const line of rawLines) {
    if (line.trim() === "") {
      pushBlock();
      blocks.push({ lines: [""], hasCitation: false, isHeading: false });
      continue;
    }
    current.push(line);
    if (CITATION_RE.test(line)) hasCitation = true;
    if (!line.trim().startsWith("#")) isHeading = false;
  }
  pushBlock();

  const include = blocks.map((b) => b.hasCitation);
  for (let i = 0; i < blocks.length; i += 1) {
    if (!include[i]) continue;
    let j = i - 1;
    while (
      j >= 0 &&
      blocks[j].lines.length === 1 &&
      blocks[j].lines[0] === ""
    ) {
      j -= 1;
    }
    if (j >= 0 && blocks[j].isHeading) include[j] = true;
  }

  const out: string[] = [];
  let lastBlank = true;
  for (let i = 0; i < blocks.length; i += 1) {
    const block = blocks[i];
    const isBlankBlock = block.lines.length === 1 && block.lines[0] === "";
    if (isBlankBlock) {
      if (!lastBlank && out.length > 0) {
        out.push("");
        lastBlank = true;
      }
      continue;
    }
    if (!include[i]) continue;
    out.push(...block.lines);
    lastBlank = false;
  }
  while (out.length > 0 && out[out.length - 1] === "") out.pop();
  return out;
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

  const [draftEvidenceIds, setDraftEvidenceIds] = useState<string[]>([]);
  const [draftInstructions, setDraftInstructions] = useState("");
  const [draftResult, setDraftResult] = useState<DraftResponse | null>(null);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [isDrafting, setIsDrafting] = useState(false);
  const [showCitedOnly, setShowCitedOnly] = useState(false);

  const [gapResult, setGapResult] = useState<GapSuggestionResponse | null>(null);
  const [gapError, setGapError] = useState<string | null>(null);
  const [isSuggestingGaps, setIsSuggestingGaps] = useState(false);

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

  useEffect(() => {
    const mappedIds = mappings.map((m) => m.evidence_id);
    setDraftEvidenceIds((prev) => {
      if (prev.length === 0) return mappedIds;
      const mappedSet = new Set(mappedIds);
      return prev.filter((id) => mappedSet.has(id));
    });
  }, [mappings]);

  function updateField(field: string, rawValue: string) {
    setContentDraft((prev) => ({ ...prev, [field]: parseEditorValue(rawValue) }));
  }

  async function generateDraft() {
    setDraftError(null);
    setDraftResult(null);
    if (!accessToken) return;
    if (!canEdit) {
      setDraftError("Editor role required to use LLM Assist.");
      return;
    }

    setIsDrafting(true);
    try {
      const data = await apiRequest<DraftResponse>(
        `/api/llm/sections/${encodeURIComponent(sectionKey)}/draft`,
        {
          method: "POST",
          body: JSON.stringify({
            version_id: versionId,
            selected_evidence_ids: draftEvidenceIds,
            instructions: draftInstructions.trim() ? draftInstructions.trim() : null,
          }),
        },
        { accessToken },
      );
      setDraftResult(data);
      setShowCitedOnly(true);
    } catch (err) {
      if (err instanceof ApiError && err.status === 413) {
        setDraftError("Too much evidence selected (LLM context window exceeded).");
      } else if (err instanceof ApiError && err.status === 503) {
        setDraftError("LLM is unavailable (disabled or not configured).");
      } else {
        setDraftError(err instanceof ApiError ? "Draft generation failed." : "Unexpected error.");
      }
    } finally {
      setIsDrafting(false);
    }
  }

  async function suggestGaps() {
    setGapError(null);
    setGapResult(null);
    if (!accessToken) return;
    if (!canEdit) {
      setGapError("Editor role required to use LLM Assist.");
      return;
    }

    setIsSuggestingGaps(true);
    try {
      const data = await apiRequest<GapSuggestionResponse>(
        `/api/llm/sections/${encodeURIComponent(sectionKey)}/gaps`,
        {
          method: "POST",
          body: JSON.stringify({ version_id: versionId }),
        },
        { accessToken },
      );
      setGapResult(data);
    } catch (err) {
      setGapError(err instanceof ApiError ? "Gap suggestions failed." : "Unexpected error.");
    } finally {
      setIsSuggestingGaps(false);
    }
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

              <div className="rounded-xl border border-zinc-200 bg-white p-6">
                <h2 className="text-sm font-medium">LLM Assist</h2>
                <p className="mt-1 text-xs text-zinc-500">
                  Drafts are advisory. Verify everything against your evidence.
                </p>

                <div className="mt-4 space-y-3">
                  <div>
                    <div className="flex items-center justify-between gap-3">
                      <label className="text-xs font-medium">Evidence for draft</label>
                      <button
                        type="button"
                        onClick={() => setDraftEvidenceIds(mappings.map((m) => m.evidence_id))}
                        className="text-xs text-zinc-600 underline hover:text-zinc-800"
                        disabled={!canEdit}
                      >
                        Select all mapped
                      </button>
                    </div>
                    {mappings.length === 0 ? (
                      <div className="mt-2 text-sm text-zinc-600">
                        No mapped evidence yet. Add mappings first.
                      </div>
                    ) : (
                      <div className="mt-2 space-y-2">
                        {mappings.map((m) => {
                          const checked = draftEvidenceIds.includes(m.evidence_id);
                          return (
                            <label
                              key={m.id}
                              className="flex items-start gap-2 rounded-md border border-zinc-200 bg-zinc-50 p-2 text-sm"
                            >
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={(e) => {
                                  const next = e.target.checked;
                                  setDraftEvidenceIds((prev) => {
                                    const set = new Set(prev);
                                    if (next) set.add(m.evidence_id);
                                    else set.delete(m.evidence_id);
                                    return Array.from(set);
                                  });
                                }}
                                disabled={!canEdit}
                              />
                              <span className="min-w-0">
                                <span className="block truncate font-medium">{m.evidence.title}</span>
                                <span className="block text-xs text-zinc-500 font-mono">
                                  {m.evidence_id}
                                </span>
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  <div>
                    <label className="text-xs font-medium">Instructions (optional)</label>
                    <textarea
                      value={draftInstructions}
                      onChange={(e) => setDraftInstructions(e.target.value)}
                      rows={3}
                      disabled={!canEdit}
                      className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400 disabled:bg-zinc-50"
                      placeholder="e.g., focus on risk identification methodology…"
                    />
                  </div>

                  {draftError ? (
                    <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                      {draftError}
                    </div>
                  ) : null}

                  <button
                    type="button"
                    onClick={() => void generateDraft()}
                    disabled={!canEdit || isDrafting}
                    className="w-full rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isDrafting ? "Generating…" : "Generate draft"}
                  </button>
                </div>

                {draftResult ? (
                  <div className="mt-6 space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-xs text-zinc-500">
                          strict_mode:{" "}
                          <span className="font-mono">{String(draftResult.strict_mode)}</span>
                          {draftResult.model_info ? (
                            <>
                              {" "}
                              · model <span className="font-mono">{draftResult.model_info}</span>
                            </>
                          ) : null}
                        </div>
                        {draftResult.warnings.length > 0 ? (
                          <div className="mt-1 text-xs text-amber-700">
                            warnings: <span className="font-mono">{draftResult.warnings.join(", ")}</span>
                          </div>
                        ) : null}
                      </div>
                      <button
                        type="button"
                        onClick={() => void navigator.clipboard.writeText(draftResult.draft_text)}
                        className="rounded-md border border-zinc-200 bg-white px-2 py-1 text-xs hover:bg-zinc-50"
                      >
                        Copy
                      </button>
                    </div>

                    <div className="rounded-md border border-zinc-200 bg-zinc-50 p-3">
                      <div className="flex items-center justify-between">
                        <div className="text-xs font-medium text-zinc-700">Draft (markdown)</div>
                        <label className="flex items-center gap-2 text-xs text-zinc-600">
                          <input
                            type="checkbox"
                            checked={showCitedOnly}
                            onChange={(e) => setShowCitedOnly(e.target.checked)}
                          />
                          citations only
                        </label>
                      </div>
                      <div className="mt-2 max-h-96 overflow-auto font-mono text-xs whitespace-pre-wrap">
                        {(showCitedOnly
                          ? getCitedOnlyLines(draftResult.draft_text)
                          : draftResult.draft_text.split("\n")
                        ).map((line, idx) => {
                          const hasCitation = CITATION_RE.test(line);
                          const isHeading = /^\s*#+\s/.test(line);
                          const emphasize = hasCitation || (showCitedOnly && isHeading);
                          return (
                            <div key={idx} className={emphasize ? "text-zinc-900" : "text-zinc-400"}>
                              {line === "" ? "\u00A0" : line}
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    <div className="rounded-md border border-zinc-200 bg-white p-3">
                      <div className="text-xs font-medium text-zinc-700">Cited evidence</div>
                      {draftResult.cited_evidence_ids.length > 0 ? (
                        <ul className="mt-2 space-y-1 text-xs">
                          {draftResult.cited_evidence_ids.map((id) => {
                            const m = mappings.find((x) => x.evidence_id === id);
                            return (
                              <li key={id} className="flex items-center justify-between gap-3">
                                <span className="truncate">
                                  {m ? m.evidence.title : id}
                                </span>
                                <span className="font-mono text-zinc-500">{id.slice(0, 8)}…</span>
                              </li>
                            );
                          })}
                        </ul>
                      ) : (
                        <div className="mt-2 text-sm text-zinc-600">No citations detected.</div>
                      )}
                      {draftEvidenceIds.length > 0 ? (
                        <div className="mt-2 text-xs text-zinc-500">
                          selected: <span className="font-mono">{draftEvidenceIds.length}</span> · cited:{" "}
                          <span className="font-mono">{draftResult.cited_evidence_ids.length}</span>
                        </div>
                      ) : null}
                    </div>
                  </div>
                ) : null}

                <div className="mt-6 border-t border-zinc-200 pt-6">
                  <h3 className="text-sm font-medium">Gap suggestions</h3>
                  <p className="mt-1 text-xs text-zinc-500">
                    Helps you understand what evidence to collect. Not claims.
                  </p>

                  {gapError ? (
                    <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                      {gapError}
                    </div>
                  ) : null}

                  <button
                    type="button"
                    onClick={() => void suggestGaps()}
                    disabled={!canEdit || isSuggestingGaps}
                    className="mt-3 w-full rounded-md border border-zinc-200 bg-white px-4 py-2 text-sm hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isSuggestingGaps ? "Analyzing…" : "Suggest gaps"}
                  </button>

                  {gapResult ? (
                    <div className="mt-4 space-y-3">
                      <div className="text-xs text-zinc-600">{gapResult.disclaimer}</div>
                      {gapResult.suggestions.length === 0 ? (
                        <div className="text-sm text-zinc-600">No gaps suggested.</div>
                      ) : (
                        <ul className="space-y-2 text-sm">
                          {gapResult.suggestions.map((s) => (
                            <li key={s.field} className="rounded-md border border-zinc-200 bg-zinc-50 p-3">
                              <div className="text-xs font-medium text-zinc-700">{s.field}</div>
                              <div className="mt-1 text-xs text-zinc-600">
                                {s.artifact_types.length > 0 ? (
                                  <ul className="list-disc pl-5">
                                    {s.artifact_types.slice(0, 6).map((t) => (
                                      <li key={t}>{t}</li>
                                    ))}
                                  </ul>
                                ) : (
                                  "No artifact types suggested."
                                )}
                              </div>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          </div>
        )}
      </RequireAuth>
    </AppShell>
  );
}

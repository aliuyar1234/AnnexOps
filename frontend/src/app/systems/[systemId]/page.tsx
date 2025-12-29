"use client";

import { useAuth } from "@/components/auth/auth-provider";
import { RequireAuth } from "@/components/auth/require-auth";
import { AppShell } from "@/components/layout/app-shell";
import {
  DECISION_INFLUENCES,
  DEPLOYMENT_TYPES,
  HR_USE_CASE_TYPES,
} from "@/lib/enums";
import { ApiError, apiRequest } from "@/lib/http";
import { hasAtLeast } from "@/lib/rbac";
import type {
  SystemDetailResponse,
  SystemResponse,
  VersionDiffResponse,
  VersionListResponse,
  VersionResponse,
} from "@/lib/types";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState, type FormEvent } from "react";

export default function SystemDetailPage() {
  const { systemId } = useParams<{ systemId: string }>();
  const { accessToken, user } = useAuth();
  const canEdit = hasAtLeast(user?.role, "editor");

  const [system, setSystem] = useState<SystemDetailResponse | null>(null);
  const [versions, setVersions] = useState<VersionResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isEditing, setIsEditing] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [isSavingSystem, setIsSavingSystem] = useState(false);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [hrUseCaseType, setHrUseCaseType] = useState<string>(
    HR_USE_CASE_TYPES[0].value,
  );
  const [intendedPurpose, setIntendedPurpose] = useState("");
  const [deploymentType, setDeploymentType] = useState<string>(
    DEPLOYMENT_TYPES[0].value,
  );
  const [decisionInfluence, setDecisionInfluence] = useState<string>(
    DECISION_INFLUENCES[0].value,
  );
  const [contactName, setContactName] = useState("");
  const [contactEmail, setContactEmail] = useState("");

  const [newVersionLabel, setNewVersionLabel] = useState("");
  const [newVersionNotes, setNewVersionNotes] = useState("");
  const [createVersionError, setCreateVersionError] = useState<string | null>(null);
  const [isCreatingVersion, setIsCreatingVersion] = useState(false);

  const [compareFrom, setCompareFrom] = useState<string>("");
  const [compareTo, setCompareTo] = useState<string>("");
  const [diff, setDiff] = useState<VersionDiffResponse | null>(null);
  const [diffError, setDiffError] = useState<string | null>(null);
  const [isComparing, setIsComparing] = useState(false);

  const versionsById = useMemo(() => {
    const map = new Map<string, VersionResponse>();
    for (const v of versions) map.set(v.id, v);
    return map;
  }, [versions]);

  useEffect(() => {
    let isMounted = true;
    (async () => {
      if (!accessToken) return;

      setIsLoading(true);
      setError(null);
      try {
        const [systemData, versionsData] = await Promise.all([
          apiRequest<SystemDetailResponse>(`/api/systems/${systemId}`, {}, { accessToken }),
          apiRequest<VersionListResponse>(
            `/api/systems/${systemId}/versions?limit=100&offset=0`,
            {},
            { accessToken },
          ),
        ]);

        if (!isMounted) return;

        setSystem(systemData);
        setVersions(versionsData.items);

        setName(systemData.name);
        setDescription(systemData.description ?? "");
        setHrUseCaseType(systemData.hr_use_case_type);
        setIntendedPurpose(systemData.intended_purpose);
        setDeploymentType(systemData.deployment_type);
        setDecisionInfluence(systemData.decision_influence);
        setContactName(systemData.contact_name ?? "");
        setContactEmail(systemData.contact_email ?? "");
      } catch (err) {
        if (isMounted) {
          setError(err instanceof ApiError ? "Failed to load system." : "Unexpected error.");
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    })();

    return () => {
      isMounted = false;
    };
  }, [accessToken, systemId]);

  async function onSaveSystem(e: FormEvent) {
    e.preventDefault();
    setEditError(null);
    if (!accessToken || !system) return;
    if (!canEdit) {
      setEditError("Editor role required to edit systems.");
      return;
    }

    const patch: Record<string, unknown> = {};
    const trimmedName = name.trim();
    const trimmedDescription = description.trim();
    const trimmedPurpose = intendedPurpose.trim();
    const trimmedContactName = contactName.trim();
    const trimmedContactEmail = contactEmail.trim();

    if (trimmedName !== system.name) patch["name"] = trimmedName;
    if ((trimmedDescription || null) !== (system.description ?? null))
      patch["description"] = trimmedDescription || null;
    if (hrUseCaseType !== system.hr_use_case_type) patch["hr_use_case_type"] = hrUseCaseType;
    if (trimmedPurpose !== system.intended_purpose) patch["intended_purpose"] = trimmedPurpose;
    if (deploymentType !== system.deployment_type) patch["deployment_type"] = deploymentType;
    if (decisionInfluence !== system.decision_influence)
      patch["decision_influence"] = decisionInfluence;
    if ((trimmedContactName || null) !== (system.contact_name ?? null))
      patch["contact_name"] = trimmedContactName || null;
    if ((trimmedContactEmail || null) !== (system.contact_email ?? null))
      patch["contact_email"] = trimmedContactEmail || null;

    patch["expected_version"] = system.version;

    if (Object.keys(patch).length === 1) {
      setIsEditing(false);
      return;
    }

    setIsSavingSystem(true);
    try {
      const updated = await apiRequest<SystemResponse>(
        `/api/systems/${systemId}`,
        { method: "PATCH", body: JSON.stringify(patch) },
        { accessToken },
      );
      setSystem((prev) =>
        prev
          ? {
              ...prev,
              ...updated,
            }
          : (updated as SystemDetailResponse),
      );
      setIsEditing(false);
    } catch (err) {
      setEditError(err instanceof ApiError ? "Update failed." : "Unexpected error.");
    } finally {
      setIsSavingSystem(false);
    }
  }

  async function onCreateVersion(e: FormEvent) {
    e.preventDefault();
    setCreateVersionError(null);
    if (!accessToken) return;
    if (!canEdit) {
      setCreateVersionError("Editor role required to create versions.");
      return;
    }

    setIsCreatingVersion(true);
    try {
      const created = await apiRequest<VersionResponse>(
        `/api/systems/${systemId}/versions`,
        {
          method: "POST",
          body: JSON.stringify({
            label: newVersionLabel.trim(),
            notes: newVersionNotes.trim() || null,
          }),
        },
        { accessToken },
      );
      setVersions((prev) => [created, ...prev]);
      setNewVersionLabel("");
      setNewVersionNotes("");
    } catch (err) {
      setCreateVersionError(err instanceof ApiError ? "Create version failed." : "Unexpected error.");
    } finally {
      setIsCreatingVersion(false);
    }
  }

  async function onCompare() {
    setDiff(null);
    setDiffError(null);

    if (!accessToken) return;
    if (!compareFrom || !compareTo) {
      setDiffError("Select two versions to compare.");
      return;
    }
    if (compareFrom === compareTo) {
      setDiffError("Select two different versions.");
      return;
    }

    setIsComparing(true);
    try {
      const params = new URLSearchParams();
      params.set("from_version", compareFrom);
      params.set("to_version", compareTo);
      const data = await apiRequest<VersionDiffResponse>(
        `/api/systems/${systemId}/versions/compare?${params.toString()}`,
        {},
        { accessToken },
      );
      setDiff(data);
    } catch (err) {
      setDiffError(err instanceof ApiError ? "Compare failed." : "Unexpected error.");
    } finally {
      setIsComparing(false);
    }
  }

  return (
    <AppShell>
      <RequireAuth>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">System</h1>
            <div className="mt-1 text-xs text-zinc-500">
              <Link href="/systems" className="hover:underline">
                Systems
              </Link>{" "}
              / <span className="font-mono">{systemId}</span>
            </div>
          </div>
          {system && canEdit ? (
            <button
              type="button"
              onClick={() => setIsEditing((v) => !v)}
              className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm hover:bg-zinc-50"
            >
              {isEditing ? "Cancel" : "Edit"}
            </button>
          ) : null}
        </div>

        {isLoading ? (
          <div className="mt-6 text-sm text-zinc-600">Loading…</div>
        ) : error ? (
          <div className="mt-6 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : !system ? (
          <div className="mt-6 text-sm text-zinc-600">Not found.</div>
        ) : (
          <div className="mt-6 grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2 space-y-6">
              <div className="rounded-xl border border-zinc-200 bg-white p-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-lg font-semibold tracking-tight">{system.name}</div>
                    <div className="mt-1 text-xs text-zinc-500">
                      {system.hr_use_case_type} · {system.deployment_type} · {system.decision_influence}
                    </div>
                    {system.description ? (
                      <p className="mt-3 text-sm text-zinc-700">{system.description}</p>
                    ) : null}
                  </div>
                  <div className="text-right text-xs text-zinc-500">v{system.version}</div>
                </div>

                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-md border border-zinc-200 bg-zinc-50 p-3">
                    <div className="text-xs text-zinc-500">Intended purpose</div>
                    <div className="mt-1 text-sm">{system.intended_purpose}</div>
                  </div>
                  <div className="rounded-md border border-zinc-200 bg-zinc-50 p-3">
                    <div className="text-xs text-zinc-500">Contact</div>
                    <div className="mt-1 text-sm">
                      {(system.contact_name || "—") +
                        (system.contact_email ? ` · ${system.contact_email}` : "")}
                    </div>
                  </div>
                </div>

                {isEditing ? (
                  <form className="mt-6 space-y-3" onSubmit={onSaveSystem}>
                    {editError ? (
                      <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                        {editError}
                      </div>
                    ) : null}

                    <div>
                      <label className="text-xs font-medium">Name</label>
                      <input
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        required
                        className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                      />
                    </div>

                    <div>
                      <label className="text-xs font-medium">Description</label>
                      <textarea
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        rows={3}
                        className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                      />
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2">
                      <div>
                        <label className="text-xs font-medium">HR use case</label>
                        <select
                          value={hrUseCaseType}
                          onChange={(e) => setHrUseCaseType(e.target.value)}
                          className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                        >
                          {HR_USE_CASE_TYPES.map((t) => (
                            <option key={t.value} value={t.value}>
                              {t.label}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="text-xs font-medium">Deployment</label>
                        <select
                          value={deploymentType}
                          onChange={(e) => setDeploymentType(e.target.value)}
                          className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                        >
                          {DEPLOYMENT_TYPES.map((t) => (
                            <option key={t.value} value={t.value}>
                              {t.label}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <div>
                      <label className="text-xs font-medium">Decision influence</label>
                      <select
                        value={decisionInfluence}
                        onChange={(e) => setDecisionInfluence(e.target.value)}
                        className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                      >
                        {DECISION_INFLUENCES.map((t) => (
                          <option key={t.value} value={t.value}>
                            {t.label}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="text-xs font-medium">Intended purpose</label>
                      <textarea
                        value={intendedPurpose}
                        onChange={(e) => setIntendedPurpose(e.target.value)}
                        required
                        rows={4}
                        className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                      />
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2">
                      <div>
                        <label className="text-xs font-medium">Contact name</label>
                        <input
                          value={contactName}
                          onChange={(e) => setContactName(e.target.value)}
                          className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium">Contact email</label>
                        <input
                          type="email"
                          value={contactEmail}
                          onChange={(e) => setContactEmail(e.target.value)}
                          className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                        />
                      </div>
                    </div>

                    <button
                      type="submit"
                      disabled={isSavingSystem}
                      className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {isSavingSystem ? "Saving…" : "Save changes"}
                    </button>
                  </form>
                ) : null}
              </div>

              <div className="rounded-xl border border-zinc-200 bg-white p-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h2 className="text-sm font-medium">Versions</h2>
                  <div className="text-xs text-zinc-500">{versions.length} versions</div>
                </div>

                {versions.length === 0 ? (
                  <div className="mt-3 text-sm text-zinc-600">No versions yet.</div>
                ) : (
                  <ul className="mt-4 divide-y divide-zinc-100">
                    {versions.map((v) => (
                      <li key={v.id} className="py-3">
                        <div className="flex items-center justify-between gap-4">
                          <div>
                            <Link
                              href={`/systems/${systemId}/versions/${v.id}`}
                              className="text-sm font-semibold hover:underline"
                            >
                              {v.label}
                            </Link>
                            <div className="mt-1 text-xs text-zinc-500">
                              {v.status} {v.release_date ? `· ${v.release_date}` : ""}{" "}
                              {v.created_by ? `· ${v.created_by.email}` : ""}
                            </div>
                          </div>
                          <div className="text-xs text-zinc-500 font-mono">{v.id.slice(0, 8)}…</div>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}

                {canEdit ? (
                  <form className="mt-6 space-y-3" onSubmit={onCreateVersion}>
                    <h3 className="text-sm font-medium">Create version</h3>
                    <div>
                      <label className="text-xs font-medium">Label</label>
                      <input
                        value={newVersionLabel}
                        onChange={(e) => setNewVersionLabel(e.target.value)}
                        required
                        className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                        placeholder="v1.0.0"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-medium">Notes</label>
                      <textarea
                        value={newVersionNotes}
                        onChange={(e) => setNewVersionNotes(e.target.value)}
                        rows={3}
                        className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                      />
                    </div>
                    {createVersionError ? (
                      <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                        {createVersionError}
                      </div>
                    ) : null}
                    <button
                      type="submit"
                      disabled={isCreatingVersion}
                      className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {isCreatingVersion ? "Creating…" : "Create version"}
                    </button>
                  </form>
                ) : (
                  <div className="mt-6 text-sm text-zinc-600">
                    You don’t have permission to create versions.
                  </div>
                )}
              </div>

              <div className="rounded-xl border border-zinc-200 bg-white p-6">
                <h2 className="text-sm font-medium">Compare versions</h2>
                <p className="mt-1 text-xs text-zinc-500">Shows metadata-level differences.</p>

                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div>
                    <label className="text-xs font-medium">From</label>
                    <select
                      value={compareFrom}
                      onChange={(e) => setCompareFrom(e.target.value)}
                      className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                    >
                      <option value="">Select version</option>
                      {versions.map((v) => (
                        <option key={v.id} value={v.id}>
                          {v.label} ({v.status})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-medium">To</label>
                    <select
                      value={compareTo}
                      onChange={(e) => setCompareTo(e.target.value)}
                      className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                    >
                      <option value="">Select version</option>
                      {versions.map((v) => (
                        <option key={v.id} value={v.id}>
                          {v.label} ({v.status})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="mt-3 flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => void onCompare()}
                    disabled={isComparing}
                    className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isComparing ? "Comparing…" : "Compare"}
                  </button>
                  {diffError ? <div className="text-sm text-red-700">{diffError}</div> : null}
                </div>

                {diff ? (
                  <div className="mt-4 space-y-3">
                    <div className="text-xs text-zinc-500">
                      {versionsById.get(diff.from_version.id)?.label ?? diff.from_version.id} →{" "}
                      {versionsById.get(diff.to_version.id)?.label ?? diff.to_version.id} · modified{" "}
                      {diff.summary.modified}
                    </div>
                    <ul className="space-y-2">
                      {diff.changes.map((c) => (
                        <li key={c.field} className="rounded-md border border-zinc-200 bg-zinc-50 p-3">
                          <div className="text-xs font-medium text-zinc-700">{c.field}</div>
                          <div className="mt-1 grid gap-2 sm:grid-cols-2">
                            <div className="text-xs text-zinc-600">
                              <div className="text-[10px] text-zinc-500">Old</div>
                              <div className="font-mono">{c.old_value ?? "—"}</div>
                            </div>
                            <div className="text-xs text-zinc-600">
                              <div className="text-[10px] text-zinc-500">New</div>
                              <div className="font-mono">{c.new_value ?? "—"}</div>
                            </div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            </div>

            <div className="space-y-6">
              <div className="rounded-xl border border-zinc-200 bg-white p-6">
                <h2 className="text-sm font-medium">Quick stats</h2>
                <div className="mt-4 grid gap-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-600">Attachments</span>
                    <span className="font-mono">{system.attachment_count}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-600">Versions</span>
                    <span className="font-mono">{versions.length}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-600">Latest assessment</span>
                    <span className="font-mono">
                      {system.latest_assessment ? system.latest_assessment.result_label : "—"}
                    </span>
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

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
import type { SystemListResponse, SystemResponse } from "@/lib/types";
import Link from "next/link";
import { useEffect, useMemo, useState, type FormEvent } from "react";

export default function SystemsPage() {
  const { accessToken, user } = useAuth();
  const canCreate = hasAtLeast(user?.role, "editor");

  const [systems, setSystems] = useState<SystemResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [limit] = useState(20);
  const [offset, setOffset] = useState(0);
  const [useCaseType, setUseCaseType] = useState<string>("");
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
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

  const filteredSystems = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return systems;
    return systems.filter((s) => {
      const haystack = `${s.name} ${s.description ?? ""}`.toLowerCase();
      return haystack.includes(q);
    });
  }, [systems, search]);

  useEffect(() => {
    let isMounted = true;
    (async () => {
      if (!accessToken) return;
      setIsLoading(true);
      setError(null);

      const params = new URLSearchParams();
      params.set("limit", String(limit));
      params.set("offset", String(offset));
      if (useCaseType) params.set("use_case_type", useCaseType);

      try {
        const data = await apiRequest<SystemListResponse>(
          `/api/systems?${params.toString()}`,
          {},
          { accessToken },
        );
        if (isMounted) {
          setSystems(data.items);
          setTotal(data.total);
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof ApiError ? "Failed to load systems." : "Unexpected error.");
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    })();

    return () => {
      isMounted = false;
    };
  }, [accessToken, limit, offset, useCaseType]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setCreateError(null);

    if (!accessToken) return;
    if (!canCreate) {
      setCreateError("Editor role required to create systems.");
      return;
    }

    setIsCreating(true);
    try {
      await apiRequest<SystemResponse>(
        "/api/systems",
        {
          method: "POST",
          body: JSON.stringify({
            name: name.trim(),
            description: description.trim() ? description.trim() : null,
            hr_use_case_type: hrUseCaseType,
            intended_purpose: intendedPurpose.trim(),
            deployment_type: deploymentType,
            decision_influence: decisionInfluence,
            contact_name: contactName.trim() ? contactName.trim() : null,
            contact_email: contactEmail.trim() ? contactEmail.trim() : null,
          }),
        },
        { accessToken },
      );

      setName("");
      setDescription("");
      setIntendedPurpose("");
      setContactName("");
      setContactEmail("");
      setOffset(0);
    } catch (err) {
      setCreateError(err instanceof ApiError ? "Create failed." : "Unexpected error.");
    } finally {
      setIsCreating(false);
    }
  }

  const canPrev = offset > 0;
  const canNext = offset + limit < total;

  return (
    <AppShell>
      <RequireAuth>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Systems</h1>
            <p className="mt-2 text-sm text-zinc-600">AI system registry for your organization.</p>
          </div>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <div className="flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search (name/description)"
                  className="w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400 sm:w-64"
                />
                <select
                  value={useCaseType}
                  onChange={(e) => {
                    setUseCaseType(e.target.value);
                    setOffset(0);
                  }}
                  className="w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400 sm:w-64"
                >
                  <option value="">All use cases</option>
                  {HR_USE_CASE_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
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
              ) : filteredSystems.length === 0 ? (
                <div className="p-4 text-sm text-zinc-600">No systems found.</div>
              ) : (
                <ul className="divide-y divide-zinc-100">
                  {filteredSystems.map((system) => (
                    <li key={system.id} className="p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <Link
                            href={`/systems/${system.id}`}
                            className="text-sm font-semibold hover:underline"
                          >
                            {system.name}
                          </Link>
                          <div className="mt-1 text-xs text-zinc-500">
                            {system.hr_use_case_type} · {system.deployment_type} ·{" "}
                            {system.decision_influence}
                          </div>
                          {system.description ? (
                            <p className="mt-2 text-sm text-zinc-700">{system.description}</p>
                          ) : null}
                        </div>
                        <div className="text-right text-xs text-zinc-500">
                          v{system.version}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <div className="lg:col-span-2">
            <div className="rounded-xl border border-zinc-200 bg-white p-4">
              <h2 className="text-sm font-medium">Create system</h2>
              <p className="mt-1 text-xs text-zinc-500">
                Requires <span className="font-mono">editor</span> or higher.
              </p>

              {!canCreate ? (
                <div className="mt-3 rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-600">
                  You don’t have permission to create systems.
                </div>
              ) : (
                <form className="mt-4 space-y-3" onSubmit={onCreate}>
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

                  {createError ? (
                    <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                      {createError}
                    </div>
                  ) : null}

                  <button
                    type="submit"
                    disabled={isCreating}
                    className="w-full rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isCreating ? "Creating…" : "Create system"}
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


"use client";

import { useAuth } from "@/components/auth/auth-provider";
import { RequireRole } from "@/components/auth/require-role";
import { AppShell } from "@/components/layout/app-shell";
import { ApiError, apiRequest } from "@/lib/http";
import { getOrgIdFromAccessToken } from "@/lib/jwt";
import type { OrganizationResponse } from "@/lib/types";
import { useEffect, useMemo, useState, type FormEvent } from "react";

export default function AdminOrganizationPage() {
  const { accessToken } = useAuth();
  const orgId = useMemo(
    () => (accessToken ? getOrgIdFromAccessToken(accessToken) : null),
    [accessToken],
  );

  const [organization, setOrganization] = useState<OrganizationResponse | null>(
    null,
  );
  const [name, setName] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    (async () => {
      if (!accessToken || !orgId) {
        if (isMounted) {
          setError("Unable to determine organization. Please re-login.");
          setIsLoading(false);
        }
        return;
      }

      setIsLoading(true);
      setError(null);
      try {
        const org = await apiRequest<OrganizationResponse>(
          `/api/organizations/${orgId}`,
          {},
          { accessToken },
        );
        if (isMounted) {
          setOrganization(org);
          setName(org.name);
        }
      } catch (err) {
        if (isMounted) {
          setError(
            err instanceof ApiError ? "Failed to load organization." : "Unexpected error.",
          );
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    })();
    return () => {
      isMounted = false;
    };
  }, [accessToken, orgId]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSuccess(null);
    setError(null);

    if (!accessToken || !orgId) {
      setError("Unable to determine organization. Please re-login.");
      return;
    }

    setIsSaving(true);
    try {
      const org = await apiRequest<OrganizationResponse>(
        `/api/organizations/${orgId}`,
        {
          method: "PATCH",
          body: JSON.stringify({ name: name.trim() }),
        },
        { accessToken },
      );
      setOrganization(org);
      setName(org.name);
      setSuccess("Organization updated.");
    } catch (err) {
      setError(err instanceof ApiError ? "Update failed." : "Unexpected error.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <AppShell>
      <RequireRole role="admin">
        <h1 className="text-xl font-semibold tracking-tight">Organization</h1>
        <p className="mt-2 text-sm text-zinc-600">Manage your organization settings.</p>

        <div className="mt-6 rounded-xl border border-zinc-200 bg-white p-6">
          {isLoading ? (
            <div className="text-sm text-zinc-600">Loading…</div>
          ) : error ? (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          ) : organization ? (
            <form className="space-y-4" onSubmit={onSubmit}>
              <div>
                <label className="text-sm font-medium">Name</label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                />
              </div>

              {success ? (
                <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                  {success}
                </div>
              ) : null}

              <button
                type="submit"
                disabled={isSaving}
                className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSaving ? "Saving…" : "Save"}
              </button>
            </form>
          ) : (
            <div className="text-sm text-zinc-600">No organization found.</div>
          )}
        </div>
      </RequireRole>
    </AppShell>
  );
}


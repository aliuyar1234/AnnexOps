"use client";

import { useAuth } from "@/components/auth/auth-provider";
import { RequireRole } from "@/components/auth/require-role";
import { AppShell } from "@/components/layout/app-shell";
import { ApiError, apiRequest } from "@/lib/http";
import type { UserResponse } from "@/lib/types";
import { useEffect, useState } from "react";

const ROLES: Array<UserResponse["role"]> = ["viewer", "reviewer", "editor", "admin"];

export default function AdminUsersPage() {
  const { accessToken } = useAuth();
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refreshUsers() {
    if (!accessToken) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiRequest<UserResponse[]>("/api/users", {}, { accessToken });
      setUsers(data);
    } catch (err) {
      setError(err instanceof ApiError ? "Failed to load users." : "Unexpected error.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void refreshUsers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken]);

  async function updateUser(userId: string, patch: { role?: string; is_active?: boolean }) {
    if (!accessToken) return;
    setError(null);
    try {
      const updated = await apiRequest<UserResponse>(
        `/api/users/${userId}`,
        { method: "PATCH", body: JSON.stringify(patch) },
        { accessToken },
      );
      setUsers((prev) => prev.map((u) => (u.id === userId ? updated : u)));
    } catch (err) {
      setError(
        err instanceof ApiError
          ? "Update failed. Check constraints (e.g., last admin)."
          : "Unexpected error.",
      );
    }
  }

  return (
    <AppShell>
      <RequireRole role="admin">
        <h1 className="text-xl font-semibold tracking-tight">Users</h1>
        <p className="mt-2 text-sm text-zinc-600">Manage access, roles, and activation.</p>

        <div className="mt-6 rounded-xl border border-zinc-200 bg-white p-6">
          {error ? (
            <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          ) : null}

          {isLoading ? (
            <div className="text-sm text-zinc-600">Loading…</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b border-zinc-200 text-xs text-zinc-500">
                    <th className="py-2 pr-4">Email</th>
                    <th className="py-2 pr-4">Role</th>
                    <th className="py-2 pr-4">Active</th>
                    <th className="py-2 pr-4">Last login</th>
                    <th className="py-2 pr-4">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} className="border-b border-zinc-100">
                      <td className="py-2 pr-4 font-mono text-xs">{u.email}</td>
                      <td className="py-2 pr-4">
                        <select
                          className="rounded-md border border-zinc-200 bg-white px-2 py-1 text-sm"
                          value={u.role}
                          onChange={(e) => void updateUser(u.id, { role: e.target.value })}
                        >
                          {ROLES.map((r) => (
                            <option key={r} value={r}>
                              {r}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="py-2 pr-4">
                        <input
                          type="checkbox"
                          checked={u.is_active}
                          onChange={(e) => void updateUser(u.id, { is_active: e.target.checked })}
                        />
                      </td>
                      <td className="py-2 pr-4 text-xs text-zinc-600">{u.last_login_at ?? "—"}</td>
                      <td className="py-2 pr-4 text-xs text-zinc-600">{u.created_at}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="mt-4">
            <button
              type="button"
              onClick={() => void refreshUsers()}
              className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm hover:bg-zinc-50"
            >
              Refresh
            </button>
          </div>
        </div>
      </RequireRole>
    </AppShell>
  );
}


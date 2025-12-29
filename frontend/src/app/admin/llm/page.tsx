"use client";

import { useAuth } from "@/components/auth/auth-provider";
import { RequireRole } from "@/components/auth/require-role";
import { AppShell } from "@/components/layout/app-shell";
import { ApiError, apiRequest } from "@/lib/http";
import { useEffect, useState } from "react";

type LlmStatusResponse = {
  llm_enabled: boolean;
  llm_available: boolean;
  provider: string;
  model: string;
  provider_configured: boolean;
};

type LlmUsageTotals = {
  interactions: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  avg_duration_ms: number | null;
};

type LlmUsageDay = {
  day: string;
  interactions: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
};

type LlmUsageResponse = {
  all_time: LlmUsageTotals;
  period_days: number;
  period: LlmUsageTotals;
  by_day: LlmUsageDay[];
};

function formatDay(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toISOString().slice(0, 10);
}

export default function AdminLlmPage() {
  const { accessToken } = useAuth();
  const [status, setStatus] = useState<LlmStatusResponse | null>(null);
  const [usage, setUsage] = useState<LlmUsageResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [usageError, setUsageError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    (async () => {
      if (!accessToken) return;
      setIsLoading(true);
      setStatusError(null);
      setUsageError(null);
      try {
        const [statusResult, usageResult] = await Promise.allSettled([
          apiRequest<LlmStatusResponse>("/api/llm/status", {}, { accessToken }),
          apiRequest<LlmUsageResponse>("/api/llm/usage?days=30", {}, { accessToken }),
        ]);

        if (!isMounted) return;

        if (statusResult.status === "fulfilled") {
          setStatus(statusResult.value);
        } else {
          setStatus(null);
          setStatusError("Failed to load LLM status.");
        }

        if (usageResult.status === "fulfilled") {
          setUsage(usageResult.value);
        } else {
          setUsage(null);
          setUsageError("Failed to load LLM usage.");
        }
      } catch (err) {
        if (!isMounted) return;
        setStatus(null);
        setUsage(null);
        const message = err instanceof ApiError ? "Unexpected API error." : "Unexpected error.";
        setStatusError(message);
        setUsageError(message);
      } finally {
        if (isMounted) setIsLoading(false);
      }
    })();
    return () => {
      isMounted = false;
    };
  }, [accessToken]);

  return (
    <AppShell>
      <RequireRole role="admin">
        <h1 className="text-xl font-semibold tracking-tight">LLM</h1>
        <p className="mt-2 text-sm text-zinc-600">
          Server-side LLM integration status (never shows secrets).
        </p>

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <div className="rounded-xl border border-zinc-200 bg-white p-6">
            <h2 className="text-sm font-medium">Status</h2>
            {isLoading ? (
              <div className="mt-3 text-sm text-zinc-600">Loading…</div>
            ) : statusError ? (
              <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {statusError}
              </div>
            ) : status ? (
              <div className="mt-3 space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-zinc-600">Enabled</span>
                  <span className="font-mono">{String(status.llm_enabled)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-zinc-600">Provider</span>
                  <span className="font-mono">{status.provider}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-zinc-600">Model</span>
                  <span className="font-mono">{status.model}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-zinc-600">Provider configured</span>
                  <span className="font-mono">{String(status.provider_configured)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-zinc-600">Available</span>
                  <span className="font-mono">{String(status.llm_available)}</span>
                </div>

                <div className="pt-3 text-xs text-zinc-500">
                  Configure via env vars in `backend/.env` (e.g. `LLM_ENABLED`, `LLM_PROVIDER`, `ANTHROPIC_API_KEY`, `LLM_MODEL`), then restart the backend.
                </div>
              </div>
            ) : (
              <div className="mt-3 text-sm text-zinc-600">No data.</div>
            )}
          </div>

          <div className="rounded-xl border border-zinc-200 bg-white p-6">
            <h2 className="text-sm font-medium">Usage</h2>
            <p className="mt-1 text-xs text-zinc-500">Token counts are provider-reported.</p>

            {isLoading ? (
              <div className="mt-3 text-sm text-zinc-600">Loading…</div>
            ) : usageError ? (
              <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {usageError}
              </div>
            ) : usage ? (
              <div className="mt-3 space-y-4 text-sm">
                <div className="rounded-md border border-zinc-200 bg-zinc-50 p-3">
                  <div className="text-xs font-medium text-zinc-700">Last {usage.period_days} days</div>
                  <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-zinc-600">Interactions</span>
                      <span className="font-mono">{usage.period.interactions}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-zinc-600">Tokens</span>
                      <span className="font-mono">{usage.period.total_tokens}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-zinc-600">Avg duration</span>
                      <span className="font-mono">
                        {usage.period.avg_duration_ms === null ? "n/a" : `${Math.round(usage.period.avg_duration_ms)}ms`}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="rounded-md border border-zinc-200 bg-white p-3">
                  <div className="text-xs font-medium text-zinc-700">All time</div>
                  <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-zinc-600">Interactions</span>
                      <span className="font-mono">{usage.all_time.interactions}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-zinc-600">Tokens</span>
                      <span className="font-mono">{usage.all_time.total_tokens}</span>
                    </div>
                  </div>
                </div>

                <div className="rounded-md border border-zinc-200 bg-white p-3">
                  <div className="text-xs font-medium text-zinc-700">Last 14 days</div>
                  {usage.by_day.length === 0 ? (
                    <div className="mt-2 text-sm text-zinc-600">No activity.</div>
                  ) : (
                    <div className="mt-2 max-h-48 overflow-auto">
                      <table className="w-full text-xs">
                        <thead className="text-zinc-500">
                          <tr>
                            <th className="text-left font-medium">Day</th>
                            <th className="text-right font-medium">Interactions</th>
                            <th className="text-right font-medium">Tokens</th>
                          </tr>
                        </thead>
                        <tbody>
                          {usage.by_day.slice(-14).map((d) => (
                            <tr key={d.day} className="border-t border-zinc-100">
                              <td className="py-1 pr-2 font-mono text-zinc-700">{formatDay(d.day)}</td>
                              <td className="py-1 text-right font-mono">{d.interactions}</td>
                              <td className="py-1 text-right font-mono">{d.total_tokens}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="mt-3 text-sm text-zinc-600">No data.</div>
            )}
          </div>
        </div>
      </RequireRole>
    </AppShell>
  );
}


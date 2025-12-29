"use client";

import { useAuth } from "@/components/auth/auth-provider";
import { RequireAuth } from "@/components/auth/require-auth";
import { AppShell } from "@/components/layout/app-shell";
import { ApiError, apiRequest } from "@/lib/http";
import type { AssessmentResponse, WizardQuestionsResponse } from "@/lib/types";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

type AnswerState = Record<string, boolean | null>;

function labelColor(label: string): string {
  const normalized = label.toLowerCase();
  if (normalized.includes("high")) return "bg-red-50 text-red-700 border-red-200";
  if (normalized.includes("limited")) return "bg-amber-50 text-amber-700 border-amber-200";
  return "bg-emerald-50 text-emerald-700 border-emerald-200";
}

export default function HighRiskAssessmentPage() {
  const { systemId } = useParams<{ systemId: string }>();
  const { accessToken } = useAuth();

  const [questions, setQuestions] = useState<WizardQuestionsResponse | null>(null);
  const [answers, setAnswers] = useState<AnswerState>({});
  const [notes, setNotes] = useState("");

  const [history, setHistory] = useState<AssessmentResponse[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<AssessmentResponse | null>(null);

  const totalQuestions = questions?.questions.length ?? 0;
  const answeredCount = useMemo(() => {
    if (!questions) return 0;
    return questions.questions.reduce((count, q) => count + (answers[q.id] === null ? 0 : 1), 0);
  }, [answers, questions]);
  const canSubmit = totalQuestions > 0 && answeredCount === totalQuestions && !isSubmitting;

  useEffect(() => {
    let isMounted = true;
    (async () => {
      if (!accessToken) return;
      setIsLoading(true);
      setError(null);
      try {
        const [qs, historyData] = await Promise.all([
          apiRequest<WizardQuestionsResponse>(
            `/api/systems/${systemId}/high-risk-assessment/questions`,
            {},
            { accessToken },
          ),
          apiRequest<AssessmentResponse[]>(
            `/api/systems/${systemId}/high-risk-assessment`,
            {},
            { accessToken },
          ),
        ]);
        if (!isMounted) return;
        setQuestions(qs);
        setHistory(historyData);
        setAnswers((prev) => {
          const next: AnswerState = {};
          for (const q of qs.questions) next[q.id] = prev[q.id] ?? null;
          return next;
        });
      } catch (err) {
        if (!isMounted) return;
        setError(err instanceof ApiError ? "Failed to load assessment wizard." : "Unexpected error.");
      } finally {
        if (isMounted) setIsLoading(false);
      }
    })();
    return () => {
      isMounted = false;
    };
  }, [accessToken, systemId]);

  async function submit() {
    setSubmitError(null);
    if (!accessToken || !questions) return;

    const payload = {
      answers: questions.questions.map((q) => ({ question_id: q.id, answer: answers[q.id] === true })),
      notes: notes.trim() ? notes.trim() : null,
    };

    setIsSubmitting(true);
    try {
      const data = await apiRequest<AssessmentResponse>(
        `/api/systems/${systemId}/high-risk-assessment`,
        { method: "POST", body: JSON.stringify(payload) },
        { accessToken },
      );
      setResult(data);
      setHistory((prev) => [data, ...prev]);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? "Assessment submission failed." : "Unexpected error.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AppShell>
      <RequireAuth>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">High-risk assessment</h1>
            <div className="mt-1 text-xs text-zinc-500">
              <Link href={`/systems/${systemId}`} className="hover:underline">
                System
              </Link>{" "}
              / <span className="font-mono">{systemId}</span>
            </div>
          </div>
          <div className="text-right text-xs text-zinc-500">
            {totalQuestions > 0 ? (
              <div>
                {answeredCount}/{totalQuestions} answered
              </div>
            ) : null}
            {questions ? <div className="font-mono">Wizard {questions.version}</div> : null}
          </div>
        </div>

        {isLoading ? (
          <div className="mt-6 text-sm text-zinc-600">Loading…</div>
        ) : error ? (
          <div className="mt-6 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : !questions ? (
          <div className="mt-6 text-sm text-zinc-600">Not available.</div>
        ) : (
          <div className="mt-6 grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2 space-y-6">
              <div className="rounded-xl border border-zinc-200 bg-white p-6">
                <h2 className="text-sm font-medium">Wizard</h2>
                <p className="mt-1 text-xs text-zinc-500">
                  Answer all questions, then submit to get a risk label + checklist.
                </p>

                {submitError ? (
                  <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                    {submitError}
                  </div>
                ) : null}

                <div className="mt-4 space-y-4">
                  {questions.questions.map((q, idx) => (
                    <div key={q.id} className="rounded-md border border-zinc-200 bg-zinc-50 p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-xs text-zinc-500">
                            Q{idx + 1} {q.high_risk_indicator ? "· high-risk indicator" : ""}
                          </div>
                          <div className="mt-1 text-sm font-medium text-zinc-900">{q.text}</div>
                          {q.help_text ? (
                            <div className="mt-1 text-xs text-zinc-600">{q.help_text}</div>
                          ) : null}
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          <button
                            type="button"
                            onClick={() => setAnswers((prev) => ({ ...prev, [q.id]: true }))}
                            className={[
                              "rounded-md border px-3 py-2 text-xs",
                              answers[q.id] === true
                                ? "border-black bg-black text-white"
                                : "border-zinc-200 bg-white hover:bg-zinc-50",
                            ].join(" ")}
                          >
                            Yes
                          </button>
                          <button
                            type="button"
                            onClick={() => setAnswers((prev) => ({ ...prev, [q.id]: false }))}
                            className={[
                              "rounded-md border px-3 py-2 text-xs",
                              answers[q.id] === false
                                ? "border-black bg-black text-white"
                                : "border-zinc-200 bg-white hover:bg-zinc-50",
                            ].join(" ")}
                          >
                            No
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="mt-6">
                  <label className="text-xs font-medium">Notes (optional)</label>
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    rows={3}
                    className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                    placeholder="Add context for auditability…"
                  />
                </div>

                <div className="mt-4 flex items-center justify-between gap-3">
                  <div className="text-xs text-zinc-500">
                    {answeredCount < totalQuestions ? "Complete all questions to submit." : "Ready to submit."}
                  </div>
                  <button
                    type="button"
                    onClick={() => void submit()}
                    disabled={!canSubmit}
                    className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isSubmitting ? "Submitting…" : "Submit assessment"}
                  </button>
                </div>
              </div>

              {result ? (
                <div className="rounded-xl border border-zinc-200 bg-white p-6">
                  <h2 className="text-sm font-medium">Result</h2>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <span
                      className={[
                        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
                        labelColor(result.result_label),
                      ].join(" ")}
                    >
                      {result.result_label}
                    </span>
                    <span className="text-xs text-zinc-500">
                      score <span className="font-mono">{result.score}</span>
                    </span>
                  </div>
                  {result.checklist.length > 0 ? (
                    <div className="mt-4">
                      <div className="text-xs font-medium text-zinc-700">Checklist</div>
                      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-zinc-700">
                        {result.checklist.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  <div className="mt-4 rounded-md border border-zinc-200 bg-zinc-50 p-3 text-xs text-zinc-600">
                    {result.disclaimer}
                  </div>
                </div>
              ) : null}
            </div>

            <div className="space-y-6">
              <div className="rounded-xl border border-zinc-200 bg-white p-6">
                <h2 className="text-sm font-medium">History</h2>
                {history.length === 0 ? (
                  <div className="mt-3 text-sm text-zinc-600">No assessments yet.</div>
                ) : (
                  <ul className="mt-3 space-y-2">
                    {history.slice(0, 10).map((a) => (
                      <li key={a.id} className="rounded-md border border-zinc-200 bg-zinc-50 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span
                            className={[
                              "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium",
                              labelColor(a.result_label),
                            ].join(" ")}
                          >
                            {a.result_label}
                          </span>
                          <span className="text-[11px] text-zinc-500">
                            <span className="font-mono">{a.score}</span>
                          </span>
                        </div>
                        <div className="mt-1 text-[11px] text-zinc-500">
                          {new Date(a.created_at).toLocaleString()}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        )}
      </RequireAuth>
    </AppShell>
  );
}


"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="mx-auto max-w-2xl px-6 py-16">
      <h1 className="text-xl font-semibold tracking-tight">Something went wrong</h1>
      <p className="mt-2 text-sm text-zinc-600">{error.message}</p>
      <button
        type="button"
        onClick={() => reset()}
        className="mt-6 rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800"
      >
        Try again
      </button>
    </div>
  );
}


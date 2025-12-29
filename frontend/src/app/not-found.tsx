import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-2xl px-6 py-16">
      <h1 className="text-xl font-semibold tracking-tight">Page not found</h1>
      <p className="mt-2 text-sm text-zinc-600">
        The page you are looking for does not exist.
      </p>
      <div className="mt-6">
        <Link
          href="/"
          className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800"
        >
          Back to home
        </Link>
      </div>
    </div>
  );
}


"use client";

import { useAuth } from "@/components/auth/auth-provider";
import { hasAtLeast } from "@/lib/rbac";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

function NavLink({
  href,
  label,
  disabled,
}: {
  href: string;
  label: string;
  disabled?: boolean;
}) {
  const pathname = usePathname();
  const isHome = href === "/";
  const active = isHome
    ? pathname === href
    : pathname === href || pathname.startsWith(`${href}/`);

  if (disabled) {
    return (
      <span className="cursor-not-allowed rounded-md px-3 py-2 text-sm text-zinc-400">
        {label}
      </span>
    );
  }
  return (
    <Link
      href={href}
      className={`rounded-md px-3 py-2 text-sm ${
        active ? "bg-zinc-200 text-zinc-900" : "text-zinc-700 hover:bg-zinc-100"
      }`}
    >
      {label}
    </Link>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { isLoading, user, logout } = useAuth();
  const isAdmin = hasAtLeast(user?.role, "admin");

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900">
      <header className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-3">
            <Link href="/" className="text-sm font-semibold tracking-tight">
              AnnexOps
            </Link>
            <nav className="hidden items-center gap-1 sm:flex">
              <NavLink href="/" label="Home" />
              <NavLink href="/systems" label="Systems" />
              <NavLink href="/evidence" label="Evidence" />
              <NavLink href="/admin" label="Admin" disabled={!isAdmin} />
            </nav>
          </div>
          <div className="flex items-center gap-3">
            {isLoading ? (
              <span className="text-xs text-zinc-500">Loading…</span>
            ) : user ? (
              <>
                <span className="hidden text-xs text-zinc-600 sm:inline">
                  {user.email} · {user.role}
                </span>
                <button
                  type="button"
                  onClick={() => void logout()}
                  className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm hover:bg-zinc-50"
                >
                  Logout
                </button>
              </>
            ) : (
              <Link
                href="/login"
                className="rounded-md bg-black px-3 py-2 text-sm font-medium text-white hover:bg-zinc-800"
              >
                Login
              </Link>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
    </div>
  );
}

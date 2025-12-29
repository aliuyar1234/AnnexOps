"use client";

import { useAuth } from "@/components/auth/auth-provider";
import { hasAtLeast, type KnownRole } from "@/lib/rbac";
import Link from "next/link";
import type { ReactNode } from "react";

export function RequireRole({
  role,
  children,
}: {
  role: KnownRole;
  children: ReactNode;
}) {
  const { isLoading, user } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-sm text-zinc-600">
        Loading…
      </div>
    );
  }

  if (!user) {
    return (
      <div className="mx-auto max-w-xl px-6 py-16">
        <h1 className="text-xl font-semibold tracking-tight">Sign in required</h1>
        <p className="mt-2 text-sm text-zinc-600">
          You need to sign in to access this page.
        </p>
        <div className="mt-6">
          <Link
            href="/login"
            className="inline-flex items-center rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800"
          >
            Go to login
          </Link>
        </div>
      </div>
    );
  }

  if (!hasAtLeast(user.role, role)) {
    return (
      <div className="mx-auto max-w-xl px-6 py-16">
        <h1 className="text-xl font-semibold tracking-tight">Access denied</h1>
        <p className="mt-2 text-sm text-zinc-600">
          Your role <span className="font-mono">{user.role}</span> does not allow
          this action. Required: <span className="font-mono">{role}</span>.
        </p>
      </div>
    );
  }

  return <>{children}</>;
}


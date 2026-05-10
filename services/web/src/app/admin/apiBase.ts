// Source of truth for the admin page's API target. The /admin page is dev-only
// (gated in page.tsx), but it can be pointed at either the local API or the
// deployed prod API via a dropdown. Update this file when adding/renaming
// environments.
"use client";

import { useCallback, useEffect, useState } from "react";

export const ADMIN_API_TARGETS = {
  local: "http://localhost:8000",
  prod: "https://api.jeromelu.ai",
} as const;

// Web origin paired with each API target. Used by admin panels to build
// outbound links (e.g. /wiki/channel/<slug>) that should land on the same
// environment whose data is being viewed — prod data → prod web.
// Empty string for local means "same origin", so links remain relative
// when developing against localhost.
export const ADMIN_WEB_TARGETS = {
  local: "",
  prod: "https://jeromelu.ai",
} as const;

export type AdminApiTarget = keyof typeof ADMIN_API_TARGETS;

const STORAGE_KEY = "admin.apiBase";
const CHANGE_EVENT = "admin-api-base-change";

function defaultTarget(): AdminApiTarget {
  const env = process.env.NEXT_PUBLIC_API_URL ?? "";
  return env.includes("localhost") || env.includes("127.0.0.1") ? "local" : "prod";
}

function readTarget(): AdminApiTarget {
  if (typeof window === "undefined") return defaultTarget();
  const v = window.localStorage.getItem(STORAGE_KEY);
  return v === "local" || v === "prod" ? v : defaultTarget();
}

export function useAdminApiBase(): {
  base: string;
  webBase: string;
  target: AdminApiTarget;
  setTarget: (t: AdminApiTarget) => void;
} {
  const [target, setTargetState] = useState<AdminApiTarget>(defaultTarget);

  // Hydrate from localStorage after mount to avoid SSR/CSR mismatch.
  useEffect(() => {
    setTargetState(readTarget());
  }, []);

  // Sync across components in the same tab (storage event doesn't fire on self).
  useEffect(() => {
    const onChange = (e: Event) => {
      const detail = (e as CustomEvent<AdminApiTarget>).detail;
      if (detail === "local" || detail === "prod") setTargetState(detail);
    };
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY && (e.newValue === "local" || e.newValue === "prod")) {
        setTargetState(e.newValue);
      }
    };
    window.addEventListener(CHANGE_EVENT, onChange);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(CHANGE_EVENT, onChange);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  const setTarget = useCallback((t: AdminApiTarget) => {
    window.localStorage.setItem(STORAGE_KEY, t);
    window.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: t }));
    setTargetState(t);
  }, []);

  return {
    base: ADMIN_API_TARGETS[target],
    webBase: ADMIN_WEB_TARGETS[target],
    target,
    setTarget,
  };
}

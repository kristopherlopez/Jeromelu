"use client";

import { usePathname } from "next/navigation";

/** Returns true when the current route is under /wiki */
export function useIsWiki(): boolean {
  const pathname = usePathname();
  return pathname.startsWith("/wiki");
}

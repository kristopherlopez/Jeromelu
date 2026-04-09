"use client";

import { usePathname } from "next/navigation";

/** Light-themed routes — avatar and nav chrome adapt accordingly */
const LIGHT_PREFIX_ROUTES = ["/wiki"];

/** Returns true when the current route uses the light (parchment) theme */
export function useIsLightTheme(): boolean {
  const pathname = usePathname();
  return pathname === "/" || LIGHT_PREFIX_ROUTES.some((r) => pathname.startsWith(r));
}

/** @deprecated Use useIsLightTheme instead */
export const useIsWiki = useIsLightTheme;

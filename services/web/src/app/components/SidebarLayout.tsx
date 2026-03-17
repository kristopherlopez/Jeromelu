"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

export default function SidebarLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const hasSidebar = pathname !== "/";

  return (
    <div className={hasSidebar ? "lg:pl-14" : undefined}>
      {children}
    </div>
  );
}

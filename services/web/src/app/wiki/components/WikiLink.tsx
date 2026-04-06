"use client";

import Link from "next/link";
import type { ReactNode } from "react";

interface WikiLinkProps {
  href: string;
  children: ReactNode;
}

export default function WikiLink({ href, children }: WikiLinkProps) {
  return (
    <Link
      href={href}
      className="font-medium no-underline hover:underline transition-colors"
      style={{ color: "var(--wiki-accent, #b85c38)" }}
    >
      {children}
    </Link>
  );
}

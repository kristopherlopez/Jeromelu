"use client";

import type { ReactNode } from "react";
import { AvatarEngineProvider } from "./AvatarEngine";
import { JeromeluPresence } from "./JeromeluPresence";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <AvatarEngineProvider>
      <JeromeluPresence />
      {children}
    </AvatarEngineProvider>
  );
}

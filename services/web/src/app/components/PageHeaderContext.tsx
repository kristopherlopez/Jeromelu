"use client";

import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export interface PageHeaderState {
  backHref?: string;
  backLabel?: string;
  title?: string;
  meta?: ReactNode;
}

interface ContextValue {
  header: PageHeaderState | null;
  setHeader: (h: PageHeaderState | null) => void;
}

const PageHeaderContext = createContext<ContextValue>({
  header: null,
  setHeader: () => {},
});

export function PageHeaderProvider({ children }: { children: ReactNode }) {
  const [header, setHeader] = useState<PageHeaderState | null>(null);
  const value = useMemo(() => ({ header, setHeader }), [header]);
  return (
    <PageHeaderContext.Provider value={value}>
      {children}
    </PageHeaderContext.Provider>
  );
}

export function usePageHeader() {
  return useContext(PageHeaderContext);
}

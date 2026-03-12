"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

interface NavHoverState {
  hoveredHref: string | null;
  setHoveredHref: (href: string | null) => void;
}

const NavHoverContext = createContext<NavHoverState>({
  hoveredHref: null,
  setHoveredHref: () => {},
});

export function NavHoverProvider({ children }: { children: ReactNode }) {
  const [hoveredHref, setHoveredHref] = useState<string | null>(null);
  return (
    <NavHoverContext.Provider value={{ hoveredHref, setHoveredHref }}>
      {children}
    </NavHoverContext.Provider>
  );
}

export function useNavHover() {
  return useContext(NavHoverContext);
}

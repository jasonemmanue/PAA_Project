"use client";

/**
 * Wrapper autour de next-themes pour fournir le thème clair / sombre.
 * `attribute="class"` ajoute la classe `.dark` sur <html> ce qui active
 * automatiquement toutes les variantes `dark:` de Tailwind.
 */

import { ThemeProvider as NextThemeProvider } from "next-themes";
import type { ReactNode } from "react";

export function ThemeProvider({ children }: { children: ReactNode }) {
  return (
    <NextThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      storageKey="paa-theme"
      disableTransitionOnChange
    >
      {children}
    </NextThemeProvider>
  );
}

/**
 * Layout racine de l'application Next.js — App Router.
 *
 * Hiérarchie des providers (du plus extérieur au plus intérieur) :
 *   ThemeProvider (next-themes) → I18nProvider (FR/EN) → AppShell (UI)
 *
 * La langue par défaut est lue depuis NEXT_PUBLIC_DEFAULT_LANG ("fr" par
 * défaut) ; un effet côté client la remplace par la valeur stockée dans
 * localStorage si elle existe.
 */

import type { ReactNode } from "react";

import "./globals.css";

import { AppShell } from "@/components/layout/AppShell";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { I18nProvider, type Locale } from "@/lib/i18n";

export const metadata = {
  title: "PAA-Traverse — Suivi des temps de traversée",
  description:
    "Application de cartographie temps réel et d'analyse des temps de traversée des axes routiers stratégiques du Port Autonome d'Abidjan.",
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0B2545",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  const langueDefaut: Locale =
    (process.env.NEXT_PUBLIC_DEFAULT_LANG as Locale | undefined) ?? "fr";

  return (
    <html lang={langueDefaut} suppressHydrationWarning>
      <body className="antialiased">
        <ThemeProvider>
          <I18nProvider defaultLocale={langueDefaut}>
            <AppShell>{children}</AppShell>
          </I18nProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}

/**
 * Layout racine de l'application Next.js — App Router.
 *
 * Hiérarchie des providers (du plus extérieur au plus intérieur) :
 *   ThemeProvider (next-themes) → I18nProvider (FR/EN) → AppShell (UI)
 *
 * Le SplashScreen est rendu en sœur de l'AppShell pour rester en
 * position fixe au-dessus de toute l'app sans bloquer son chargement.
 *
 * La langue par défaut est lue depuis NEXT_PUBLIC_DEFAULT_LANG ("fr" par
 * défaut) ; un effet côté client la remplace par la valeur stockée dans
 * localStorage si elle existe.
 */

import type { ReactNode } from "react";

import "./globals.css";

import { ClientLayout } from "@/components/layout/ClientLayout";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { I18nProvider, type Locale } from "@/lib/i18n";

export const metadata = {
  title: "PAA-Traverse | Port Autonome d'Abidjan",
  description:
    "Suivi en temps réel et analyse historique des temps de traversée des axes routiers stratégiques du Port Autonome d'Abidjan. Cartographie dynamique, indicateurs FHWA et recommandations opérationnelles.",
  applicationName: "PAA-Traverse",
  authors: [{ name: "Team HACKATONIA" }],
  keywords: [
    "PAA",
    "Port Autonome d'Abidjan",
    "trafic",
    "congestion",
    "temps de traversée",
    "HACKATONIA",
  ],
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/icon-192.png", type: "image/png", sizes: "192x192" },
      { url: "/icon-512.png", type: "image/png", sizes: "512x512" },
    ],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180" }],
  },
  openGraph: {
    title: "PAA-Traverse | Port Autonome d'Abidjan",
    description:
      "Cartographie temps réel et analyse des temps de traversée — projet Team HACKATONIA.",
    type: "website",
  },
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
            <ClientLayout>{children}</ClientLayout>
          </I18nProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}

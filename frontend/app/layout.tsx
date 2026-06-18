// Layout racine de l'application Next.js — squelette minimal pour la phase P1.
// L'i18n, le thème clair/sombre et la mise en page responsive seront ajoutés en P4.

import type { ReactNode } from "react";

export const metadata = {
  title: "PAA-Traverse",
  description:
    "Suivi en temps réel des temps de traversée des axes routiers du Port Autonome d'Abidjan.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}

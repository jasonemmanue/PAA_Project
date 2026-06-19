"use client";

/**
 * Bouton de bascule clair / sombre. Affiche une icône soleil ou lune
 * selon le thème actif. Pleinement accessible (aria-label traduit).
 */

import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { useI18n } from "@/lib/i18n";

export function ThemeToggle() {
  const { theme, resolvedTheme, setTheme } = useTheme();
  const { t } = useI18n();
  const [monte, setMonte] = useState(false);

  // Évite un mismatch SSR/CSR : on n'affiche le bon état qu'après hydration
  useEffect(() => setMonte(true), []);

  const themeCourant = resolvedTheme ?? theme ?? "light";
  const estSombre = themeCourant === "dark";
  const prochainTheme = estSombre ? "light" : "dark";
  const label = estSombre
    ? `${t("common.theme")} : ${t("common.themeLight")}`
    : `${t("common.theme")} : ${t("common.themeDark")}`;

  return (
    <button
      type="button"
      onClick={() => setTheme(prochainTheme)}
      aria-label={label}
      title={label}
      className="inline-flex h-10 w-10 items-center justify-center rounded-md
                 border border-white/20 bg-white/10 text-white transition-colors
                 hover:bg-white/20 focus:outline-none focus:ring-2
                 focus:ring-paa-blue-400"
    >
      {/* L'icône réelle dépend du thème, mais on rend un placeholder neutre
          tant que React n'a pas hydraté pour éviter un flash visuel. */}
      {monte ? (estSombre ? <IconeSoleil /> : <IconeLune />) : <IconeLune />}
    </button>
  );
}

function IconeSoleil() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  );
}

function IconeLune() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

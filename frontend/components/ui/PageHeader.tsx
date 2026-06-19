"use client";

/**
 * En-tête de page standard — titre principal et sous-titre.
 * Toutes les pages métier l'utilisent pour rester cohérentes.
 */

import type { ReactNode } from "react";

export function PageHeader({
  titre,
  sousTitre,
  actions,
}: {
  titre: string;
  sousTitre?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-fluid-6 flex flex-col gap-3 sm:gap-2 md:flex-row md:items-end md:justify-between">
      <div className="min-w-0">
        <h1 className="text-fluid-2xl font-bold tracking-tight">{titre}</h1>
        {sousTitre && (
          <p className="mt-1 text-fluid-sm app-text-muted">{sousTitre}</p>
        )}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

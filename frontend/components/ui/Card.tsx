"use client";

import clsx from "clsx";
import type { ReactNode } from "react";

/**
 * Carte conteneur standard — fond clair, bordure subtile, ombre paa-sm.
 * S'adapte automatiquement au mode sombre via la classe `app-surface`.
 */
export function Card({
  children,
  className,
  titre,
  description,
}: {
  children?: ReactNode;
  className?: string;
  titre?: string;
  description?: string;
}) {
  return (
    <section className={clsx("paa-card p-fluid-4", className)}>
      {(titre || description) && (
        <header className="mb-3">
          {titre && <h2 className="text-fluid-lg font-semibold">{titre}</h2>}
          {description && (
            <p className="mt-1 text-fluid-sm app-text-muted">{description}</p>
          )}
        </header>
      )}
      {children}
    </section>
  );
}

/**
 * Placeholder réutilisable pour le contenu à venir (carte, graphique, etc.).
 * Affiche un fond pointillé et un message explicatif.
 */
export function Placeholder({ message }: { message: string }) {
  return (
    <div
      className="flex min-h-[200px] items-center justify-center rounded-md border-2
                 border-dashed app-border app-text-muted text-center text-fluid-sm
                 px-4 py-8 md:min-h-[280px] lg:min-h-[360px]"
      role="status"
    >
      {message}
    </div>
  );
}

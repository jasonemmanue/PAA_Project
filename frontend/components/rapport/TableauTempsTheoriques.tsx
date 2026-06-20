"use client";

import { Card } from "@/components/ui/Card";
import type { RapportTempsTheoriques } from "@/lib/types";

export function TableauTempsTheoriques({
  rapport,
}: {
  rapport: RapportTempsTheoriques | null;
}) {
  return (
    <Card
      titre="Tableau 1 — Temps de traversée normal pour 50 km/h"
      description="Source : DEESP/DEEF — Code de référence : DEESP-RF-01"
    >
      <div className="overflow-x-auto">
        <table className="min-w-full text-fluid-sm">
          <thead className="bg-paa-navy-700 text-white dark:bg-paa-navy-800">
            <tr>
              <Th>AXE</Th>
              <Th>DISTANCE</Th>
              <Th>TEMPS MOYEN DE TRAVERSÉE POUR UNE VITESSE DE 50 KM/H</Th>
            </tr>
          </thead>
          <tbody>
            {(rapport?.lignes ?? []).map((l) => (
              <tr key={l.axe} className="border-t app-border">
                <Td>{l.axe}</Td>
                <Td>{l.distance_km.toLocaleString("fr-FR")} km</Td>
                <Td>{l.temps_50kmh}</Td>
              </tr>
            ))}
            {!rapport && (
              <tr>
                <Td colSpan={3}>
                  <span className="app-text-muted">Chargement…</span>
                </Td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="px-3 py-2 text-left text-fluid-xs font-medium uppercase tracking-wide">{children}</th>;
}

function Td({ children, colSpan }: { children: React.ReactNode; colSpan?: number }) {
  return (
    <td colSpan={colSpan} className="px-3 py-2 align-top text-paa-navy-900 dark:text-paa-blue-100">
      {children}
    </td>
  );
}

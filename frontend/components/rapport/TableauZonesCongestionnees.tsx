"use client";

import { Card } from "@/components/ui/Card";
import type { RapportZonesCongestionnees } from "@/lib/types";

export function TableauZonesCongestionnees({
  rapport,
}: {
  rapport: RapportZonesCongestionnees | null;
}) {
  return (
    <Card
      titre="Tableau 16 — Tronçons congestionnés (règles DEESP)"
      description={
        "Tronçon congestionné si : (a) ≥ 3 occurrences sur un jour-indicatif " +
        "à la même heure, OU (b) ≥ 4 occurrences à la même heure dans la semaine. " +
        "Critère de congestion : duree_trafic_s > 1.5 × T_ref_50kmh."
      }
    >
      <div className="overflow-x-auto">
        <table className="min-w-full text-fluid-sm">
          <thead className="bg-paa-navy-700 text-white dark:bg-paa-navy-800">
            <tr>
              <Th>TRONÇON</Th>
              <Th>TRANCHE HORAIRE</Th>
              <Th className="text-right">NB / SEMAINE</Th>
              <Th>RÈGLE DÉCLENCHÉE</Th>
              <Th>RÉPARTITION PAR JOUR</Th>
            </tr>
          </thead>
          <tbody>
            {(rapport?.entrees ?? []).map((e) => (
              <tr key={`${e.troncon_id}-${e.heure}`} className="border-t app-border">
                <Td>{e.troncon_nom}</Td>
                <Td className="font-mono">{e.tranche}</Td>
                <Td className="text-right font-semibold">{e.nb_total_semaine}</Td>
                <Td>
                  {e.regle_jour_indicatif && (
                    <span className="mr-2 inline-block rounded bg-statut-congestionne/20 px-2 py-0.5 text-xs text-statut-congestionne">
                      ≥ 3 / jour
                    </span>
                  )}
                  {e.regle_semaine && (
                    <span className="inline-block rounded bg-amber-500/20 px-2 py-0.5 text-xs text-amber-700 dark:text-amber-300">
                      ≥ 4 / semaine
                    </span>
                  )}
                </Td>
                <Td>
                  <div className="flex flex-wrap gap-1 text-fluid-xs">
                    {Object.entries(e.nb_par_jour_semaine).map(([jour, nb]) => (
                      <span
                        key={jour}
                        className="rounded bg-paa-blue-50 px-1.5 py-0.5 dark:bg-paa-navy-800"
                      >
                        {jour}: {nb}
                      </span>
                    ))}
                  </div>
                </Td>
              </tr>
            ))}
            {(rapport?.entrees ?? []).length === 0 && (
              <tr>
                <Td colSpan={5}>
                  <span className="app-text-muted">
                    {rapport
                      ? "Aucun tronçon congestionné sur cette campagne — conforme aux observations DEESP de la zone portuaire."
                      : "Chargement…"}
                  </span>
                </Td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <th className={`px-3 py-2 text-left text-fluid-xs font-medium uppercase tracking-wide ${className ?? ""}`}>
      {children}
    </th>
  );
}

function Td({
  children,
  colSpan,
  className,
}: {
  children: React.ReactNode;
  colSpan?: number;
  className?: string;
}) {
  return (
    <td
      colSpan={colSpan}
      className={`px-3 py-2 align-top text-paa-navy-900 dark:text-paa-blue-100 ${className ?? ""}`}
    >
      {children}
    </td>
  );
}

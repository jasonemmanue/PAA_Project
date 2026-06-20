"use client";

import { Card } from "@/components/ui/Card";
import type { LigneTempsTraversee, RapportTempsTraversee } from "@/lib/types";

type Agregat = "min" | "moyen" | "max";

const LIBELLE: Record<Agregat, string> = {
  min: "TEMPS MINIMAL (en Mn)",
  moyen: "TEMPS MOYEN (en Mn)",
  max: "TEMPS MAXIMAL (en Mn)",
};

function valeurAgregat(l: LigneTempsTraversee, agregat: Agregat): number | null {
  if (agregat === "min") return l.temps_min_mn;
  if (agregat === "moyen") return l.temps_moyen_mn;
  return l.temps_max_mn;
}

export function TableauTempsTraversee({
  rapport,
  agregat,
  titre,
  description,
}: {
  rapport: RapportTempsTraversee | null;
  agregat: Agregat;
  titre: string;
  description: string;
}) {
  // Group lines by troncon_nom so we can show 2 cols (jour_ouvrable / week_end)
  const parTroncon = new Map<string, { ouvrable: number | null; we: number | null }>();
  for (const l of rapport?.lignes ?? []) {
    const v = valeurAgregat(l, agregat);
    const slot = parTroncon.get(l.troncon_nom) ?? { ouvrable: null, we: null };
    if (l.type_jour === "jour_ouvrable") slot.ouvrable = v;
    else slot.we = v;
    parTroncon.set(l.troncon_nom, slot);
  }

  return (
    <Card titre={titre} description={description}>
      <div className="overflow-x-auto">
        <table className="min-w-full text-fluid-sm">
          <thead className="bg-paa-navy-700 text-white dark:bg-paa-navy-800">
            <tr>
              <Th>RUBRIQUE</Th>
              <Th>TRONÇON</Th>
              <Th className="text-right">JOURS OUVRABLES</Th>
              <Th className="text-right">WEEK-ENDS</Th>
            </tr>
          </thead>
          <tbody>
            {Array.from(parTroncon.entries()).map(([nom, vals]) => (
              <tr key={nom} className="border-t app-border">
                <Td>{LIBELLE[agregat]}</Td>
                <Td>{nom}</Td>
                <Td className="text-right font-semibold">
                  {vals.ouvrable ?? "—"}
                </Td>
                <Td className="text-right font-semibold">{vals.we ?? "—"}</Td>
              </tr>
            ))}
            {parTroncon.size === 0 && (
              <tr>
                <Td colSpan={4}>
                  <span className="app-text-muted">
                    {rapport
                      ? "Pas de mesures sur cette campagne (mois sélectionné sans données collectées)."
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

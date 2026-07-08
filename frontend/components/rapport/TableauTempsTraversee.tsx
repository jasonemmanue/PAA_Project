"use client";

import { Card } from "@/components/ui/Card";
import { formaterDuree } from "@/lib/format";
import type { LigneTempsTraversee, RapportTempsTraversee } from "@/lib/types";

type Agregat = "min" | "moyen" | "max";

const LIBELLE: Record<Agregat, string> = {
  min: "TEMPS MINIMAL",
  moyen: "TEMPS MOYEN",
  max: "TEMPS MAXIMAL",
};

function valeurSecondes(l: LigneTempsTraversee, agregat: Agregat): number | null {
  if (agregat === "min") return l.temps_min_s ?? (l.temps_min_mn != null ? l.temps_min_mn * 60 : null);
  if (agregat === "moyen") return l.temps_moyen_s ?? (l.temps_moyen_mn != null ? l.temps_moyen_mn * 60 : null);
  return l.temps_max_s ?? (l.temps_max_mn != null ? l.temps_max_mn * 60 : null);
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
  const parTroncon = new Map<string, { ouvrable: number | null; we: number | null; nbJo: number; nbWe: number }>();
  for (const l of rapport?.lignes ?? []) {
    const v = valeurSecondes(l, agregat);
    const slot = parTroncon.get(l.troncon_nom) ?? { ouvrable: null, we: null, nbJo: 0, nbWe: 0 };
    if (l.type_jour === "jour_ouvrable") { slot.ouvrable = v; slot.nbJo = l.nb_mesures; }
    else { slot.we = v; slot.nbWe = l.nb_mesures; }
    parTroncon.set(l.troncon_nom, slot);
  }

  // Ne garder que les tronçons ayant au moins 1 mesure
  const entrees = Array.from(parTroncon.entries()).filter(([, v]) => v.nbJo > 0 || v.nbWe > 0);

  return (
    <Card titre={titre} description={description}>
      <div className="overflow-x-auto">
        <table className="min-w-full text-fluid-sm">
          <thead className="bg-paa-navy-700 text-white dark:bg-paa-navy-800">
            <tr>
              <Th>RUBRIQUE</Th>
              <Th>TRONÇON</Th>
              <Th className="text-right">JOURS OUVRABLES</Th>
              <Th className="text-right">NB MESURES JO</Th>
              <Th className="text-right">WEEK-ENDS</Th>
              <Th className="text-right">NB MESURES WE</Th>
            </tr>
          </thead>
          <tbody>
            {entrees.map(([nom, vals]) => (
              <tr key={nom} className="border-t app-border">
                <Td>{LIBELLE[agregat]}</Td>
                <Td>{nom}</Td>
                <Td className={`text-right font-semibold ${vals.nbJo === 0 ? "app-text-muted italic" : ""}`}>
                  {vals.nbJo === 0 ? "aucune mesure" : vals.ouvrable != null ? formaterDuree(vals.ouvrable) : "—"}
                </Td>
                <Td className="text-right text-fluid-xs app-text-muted">{vals.nbJo}</Td>
                <Td className={`text-right font-semibold ${vals.nbWe === 0 ? "app-text-muted italic" : ""}`}>
                  {vals.nbWe === 0 ? "aucune mesure" : vals.we != null ? formaterDuree(vals.we) : "—"}
                </Td>
                <Td className="text-right text-fluid-xs app-text-muted">{vals.nbWe}</Td>
              </tr>
            ))}
            {entrees.length === 0 && (
              <tr>
                <Td colSpan={6}>
                  <span className="app-text-muted">
                    {rapport
                      ? "Aucune mesure réelle sur cette campagne."
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

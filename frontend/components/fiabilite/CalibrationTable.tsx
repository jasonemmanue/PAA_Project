"use client";

/**
 * Tableau du facteur de calibration par tronçon.
 *
 * Affiche la moyenne mobile (4 derniers relevés par défaut) ainsi que
 * l'écart le plus récent. Un code couleur signale les dérives :
 *   - vert    : |ε| ≤ 10 % (acceptable)
 *   - orange  : 10 % < |ε| ≤ 25 % (à surveiller)
 *   - rouge   : |ε| > 25 % (dérive avérée, recalibration nécessaire)
 */

import { Card } from "@/components/ui/Card";
import { useI18n } from "@/lib/i18n";
import type { CalibrationTroncon } from "@/lib/types";

function couleurEcart(ecart: number | null): string {
  if (ecart === null) return "app-text-muted";
  const abs = Math.abs(ecart);
  if (abs > 0.25) return "text-statut-congestionne font-semibold";
  if (abs > 0.1) return "text-statut-dense font-semibold";
  return "text-statut-fluide font-semibold";
}

function formaterPourcent(v: number | null): string {
  if (v === null) return "—";
  const signe = v >= 0 ? "+" : "";
  return `${signe}${(v * 100).toFixed(1)} %`;
}

export function CalibrationTable({
  troncons,
  fenetre,
}: {
  troncons: CalibrationTroncon[];
  fenetre: number;
}) {
  const { t } = useI18n();

  return (
    <Card
      titre={t("fiabilite.calibrationTitle")}
      description={t("fiabilite.calibrationDescription").replace(
        "{n}",
        String(fenetre),
      )}
    >
      <div className="overflow-x-auto">
        <table className="min-w-full text-fluid-xs">
          <thead className="bg-paa-blue-50 dark:bg-paa-navy-800">
            <tr className="text-left">
              <Th>{t("fiabilite.colTroncon")}</Th>
              <Th>{t("fiabilite.colNbReleves")}</Th>
              <Th>{t("fiabilite.colEcartMoyen")}</Th>
              <Th>{t("fiabilite.colEcartCourant")}</Th>
              <Th>{t("fiabilite.colStatut")}</Th>
            </tr>
          </thead>
          <tbody>
            {troncons.map((tr) => (
              <tr key={tr.troncon_id} className="border-t app-border">
                <Td>{tr.troncon_nom}</Td>
                <Td>{tr.nb_releves}</Td>
                <Td>
                  <span className={couleurEcart(tr.ecart_moyen)}>
                    {formaterPourcent(tr.ecart_moyen)}
                  </span>
                </Td>
                <Td>
                  <span className={couleurEcart(tr.ecart_courant)}>
                    {formaterPourcent(tr.ecart_courant)}
                  </span>
                </Td>
                <Td>
                  {tr.ecart_moyen === null
                    ? t("fiabilite.statutSansDonnees")
                    : Math.abs(tr.ecart_moyen) > 0.25
                      ? t("fiabilite.statutDerive")
                      : Math.abs(tr.ecart_moyen) > 0.1
                        ? t("fiabilite.statutSurveiller")
                        : t("fiabilite.statutValide")}
                </Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="px-2 py-2 font-medium text-paa-navy-700 dark:text-paa-blue-100">{children}</th>;
}

function Td({ children }: { children: React.ReactNode }) {
  return <td className="px-2 py-2 align-middle">{children}</td>;
}

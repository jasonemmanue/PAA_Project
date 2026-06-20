"use client";

/**
 * Page Fiabilité (P5) — orchestrateur.
 *
 * Trois blocs :
 *   1. Import GPX terrain (drag & drop simplifié).
 *   2. Évolution de l'écart relatif par tronçon (LineChart Recharts).
 *   3. Tableau de calibration (moyenne mobile par tronçon).
 *
 * Charge en parallèle au montage :
 *   - GET /troncons         (pour mapper id → nom)
 *   - GET /terrain/releves  (historique pour le graphique)
 *   - GET /terrain/calibration?fenetre=4
 *
 * Après chaque import GPX réussi, recharge releves + calibration.
 */

import { useCallback, useEffect, useState } from "react";

import { CalibrationTable } from "@/components/fiabilite/CalibrationTable";
import { EvolutionEcart } from "@/components/fiabilite/EvolutionEcart";
import { ImportGpx } from "@/components/fiabilite/ImportGpx";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type {
  CalibrationResponse,
  ReleveTerrainResponse,
  Troncon,
} from "@/lib/types";

const FENETRE_CALIBRATION = 4;

export function PageFiabilite() {
  const { t } = useI18n();
  const [troncons, setTroncons] = useState<Troncon[]>([]);
  const [releves, setReleves] = useState<ReleveTerrainResponse | null>(null);
  const [calibration, setCalibration] = useState<CalibrationResponse | null>(null);
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState<string | null>(null);

  const rechargerDonnees = useCallback(async () => {
    setChargement(true);
    setErreur(null);
    try {
      const [tr, rel, cal] = await Promise.all([
        api.troncons(),
        api.terrainReleves({ limite: 500 }),
        api.terrainCalibration(FENETRE_CALIBRATION),
      ]);
      setTroncons(Array.isArray(tr) ? tr : []);
      setReleves(rel);
      setCalibration(cal);
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setChargement(false);
    }
  }, []);

  useEffect(() => {
    rechargerDonnees();
  }, [rechargerDonnees]);

  // KPIs sommaires
  const nbReleves = releves?.nb_lignes ?? 0;
  const derniereSession = releves?.lignes[0]?.date_session ?? null;
  const tronconsValides = (calibration?.troncons ?? []).filter(
    (t) => t.ecart_moyen !== null && Math.abs(t.ecart_moyen) <= 0.1,
  ).length;
  const nbTronconsTotal = calibration?.troncons.length ?? 6;

  return (
    <div className="flex flex-col gap-fluid-4">
      <PageHeader
        titre={t("fiabilite.title")}
        sousTitre={t("fiabilite.subtitle")}
      />

      {erreur && (
        <div className="rounded-md bg-statut-congestionne/10 border border-statut-congestionne/40 px-3 py-2 text-fluid-sm text-statut-congestionne">
          {t("common.error")} : {erreur}
        </div>
      )}

      {/* Ligne KPI compacte */}
      <div className="grid gap-fluid-4 md:grid-cols-3">
        <Card titre={t("fiabilite.lastSession")}>
          <p className="text-fluid-xl font-semibold text-paa-navy-900 dark:text-paa-blue-100">
            {derniereSession ?? "—"}
          </p>
          <p className="mt-1 text-fluid-xs app-text-muted">
            {t("fiabilite.nbReleves").replace("{n}", String(nbReleves))}
          </p>
        </Card>
        <Card titre={t("fiabilite.ecartMoyen")}>
          <p className="text-fluid-xl font-semibold text-paa-navy-900 dark:text-paa-blue-100">
            {formaterEcartMoyenGlobal(calibration)}
          </p>
        </Card>
        <Card titre={t("fiabilite.tronconsValides")}>
          <p className="text-fluid-xl font-semibold text-paa-navy-900 dark:text-paa-blue-100">
            {tronconsValides} / {nbTronconsTotal}
          </p>
        </Card>
      </div>

      {/* Import GPX */}
      <ImportGpx onImporte={rechargerDonnees} />

      {/* Évolution écart */}
      <EvolutionEcart releves={releves?.lignes ?? []} troncons={troncons} />

      {/* Tableau de calibration */}
      {calibration && (
        <CalibrationTable
          troncons={calibration.troncons}
          fenetre={calibration.fenetre_relevees}
        />
      )}

      {chargement && (
        <p className="text-fluid-xs app-text-muted">{t("common.loading")}</p>
      )}
    </div>
  );
}

function formaterEcartMoyenGlobal(c: CalibrationResponse | null): string {
  if (!c) return "—";
  const ecarts = c.troncons
    .map((t) => t.ecart_moyen)
    .filter((v): v is number => v !== null);
  if (ecarts.length === 0) return "—";
  const moy = ecarts.reduce((a, b) => a + b, 0) / ecarts.length;
  const signe = moy >= 0 ? "+" : "";
  return `${signe}${(moy * 100).toFixed(1)} %`;
}

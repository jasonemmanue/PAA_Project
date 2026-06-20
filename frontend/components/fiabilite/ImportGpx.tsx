"use client";

/**
 * Bloc d'upload d'un fichier GPX terrain.
 *
 * Comportement :
 *   1. L'utilisateur choisit un .gpx → bouton "Importer" actif.
 *   2. POST vers /terrain/import.
 *   3. Affiche le résumé : nb points GPX, nb tronçons détectés.
 *   4. Tableau ligne par ligne : tronçon, T_terrain, T_API, ε, confiance.
 *
 * Après import, on signale au parent (callback `onImporte`) pour qu'il
 * recharge l'historique et la calibration.
 */

import { useState } from "react";

import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import { formaterDuree } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { ImportGpxResponse } from "@/lib/types";

export function ImportGpx({ onImporte }: { onImporte?: () => void }) {
  const { t } = useI18n();
  const [fichier, setFichier] = useState<File | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [resultat, setResultat] = useState<ImportGpxResponse | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  const importer = async () => {
    if (!fichier) return;
    setEnCours(true);
    setErreur(null);
    try {
      const res = await api.terrainImport(fichier);
      setResultat(res);
      onImporte?.();
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setEnCours(false);
    }
  };

  return (
    <Card titre={t("fiabilite.importTitle")} description={t("fiabilite.importDescription")}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <label className="flex-1">
          <span className="sr-only">{t("fiabilite.choisirFichier")}</span>
          <input
            type="file"
            accept=".gpx,application/gpx+xml"
            onChange={(e) => {
              setFichier(e.target.files?.[0] ?? null);
              setResultat(null);
              setErreur(null);
            }}
            className="block w-full text-fluid-sm text-paa-navy-700 dark:text-paa-blue-100
                       file:mr-3 file:rounded-md file:border-0 file:bg-paa-navy-700 file:px-3
                       file:py-2 file:text-fluid-sm file:font-medium file:text-white
                       file:hover:bg-paa-navy-800 file:cursor-pointer"
          />
        </label>
        <button
          type="button"
          onClick={importer}
          disabled={!fichier || enCours}
          className="btn-primary disabled:opacity-50"
        >
          {enCours ? t("common.loading") : t("fiabilite.btnImporter")}
        </button>
      </div>

      {erreur && (
        <p className="mt-3 rounded-md bg-statut-congestionne/10 border border-statut-congestionne/40 px-3 py-2 text-fluid-sm text-statut-congestionne">
          {erreur}
        </p>
      )}

      {resultat && (
        <div className="mt-4 flex flex-col gap-3">
          <div className="grid gap-2 text-fluid-xs sm:grid-cols-3">
            <Info
              label={t("fiabilite.dateSession")}
              valeur={resultat.date_session}
            />
            <Info
              label={t("fiabilite.nbPointsGpx")}
              valeur={resultat.nb_points_gpx.toLocaleString("fr-FR")}
            />
            <Info
              label={t("fiabilite.nbTronconsDetectes")}
              valeur={`${resultat.nb_troncons_detectes} / 6`}
            />
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full text-fluid-xs">
              <thead className="bg-paa-blue-50 dark:bg-paa-navy-800">
                <tr className="text-left">
                  <Th>{t("fiabilite.colTroncon")}</Th>
                  <Th>{t("fiabilite.colTerrain")}</Th>
                  <Th>{t("fiabilite.colApi")}</Th>
                  <Th>ε</Th>
                  <Th>{t("fiabilite.colConfiance")}</Th>
                </tr>
              </thead>
              <tbody>
                {resultat.releves.map((r) => (
                  <tr key={r.id} className="border-t app-border">
                    <Td>{r.troncon_nom}</Td>
                    <Td>{formaterDuree(r.duree_terrain_s)}</Td>
                    <Td>{formaterDuree(r.duree_api_s)}</Td>
                    <Td>
                      {r.ecart_relatif === null ? (
                        <span className="app-text-muted">—</span>
                      ) : (
                        <span
                          className={
                            Math.abs(r.ecart_relatif) > 0.15
                              ? "text-statut-congestionne font-semibold"
                              : "text-statut-fluide"
                          }
                        >
                          {(r.ecart_relatif * 100).toFixed(1)} %
                        </span>
                      )}
                    </Td>
                    <Td>
                      {r.confiance_matching === null
                        ? "—"
                        : (r.confiance_matching * 100).toFixed(0) + " %"}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Card>
  );
}

function Info({ label, valeur }: { label: string; valeur: string }) {
  return (
    <div className="rounded-md border app-border px-3 py-2 app-surface">
      <div className="app-text-muted">{label}</div>
      <div className="font-semibold text-paa-navy-900 dark:text-paa-blue-100">
        {valeur}
      </div>
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="px-2 py-2 font-medium text-paa-navy-700 dark:text-paa-blue-100">{children}</th>;
}

function Td({ children }: { children: React.ReactNode }) {
  return <td className="px-2 py-2 align-middle">{children}</td>;
}

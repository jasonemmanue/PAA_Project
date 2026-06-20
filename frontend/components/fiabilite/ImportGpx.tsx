"use client";

/**
 * Bloc d'upload d'un ou plusieurs fichiers GPX terrain.
 *
 * Comportement :
 *   1. L'utilisateur choisit 1..N .gpx (sélection multiple supportée).
 *   2. Bouton "Importer" → boucle séquentielle d'appels POST /terrain/import.
 *   3. Indicateur de progression "{n} / {total}".
 *   4. Tableau récapitulatif consolidé : chaque ligne = un tronçon détecté,
 *      avec le nom du fichier d'origine pour la traçabilité.
 *
 * Pourquoi séquentiel et pas parallèle :
 *   - Chaque import écrit dans `releves_terrain` et déclenche un INSERT.
 *     Le séquentiel évite les pics de connexions DB sur un upload de 6+ GPX.
 *   - L'écart de quelques secondes entre 2 fichiers est négligeable côté UX.
 *
 * Après chaque succès, on signale au parent (`onImporte`) pour qu'il rafraîchisse
 * l'historique et la calibration au fur et à mesure (les graphiques se peuplent
 * progressivement).
 */

import { useMemo, useState } from "react";

import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import { formaterDuree } from "@/lib/format";
import { parserGpxFichier, type TraceGpx } from "@/lib/gpxClient";
import { useI18n } from "@/lib/i18n";
import type { ImportGpxResponse, ReleveTerrainImport } from "@/lib/types";

interface ResultatFichier {
  nomFichier: string;
  reponse: ImportGpxResponse | null;
  erreur: string | null;
}

interface ImportGpxProps {
  /** Appelé après chaque upload réussi pour rafraîchir l'historique. */
  onImporte?: () => void;
  /**
   * Appelé dès qu'au moins un fichier est sélectionné — fournit les traces
   * parsées côté client pour la prévisualisation carte.
   */
  onTracesChange?: (traces: TraceGpx[]) => void;
  /**
   * Appelé après chaque upload réussi — fournit les relevés détectés pour
   * placer les marqueurs de début/fin sur la carte.
   */
  onRelevesChange?: (releves: ReleveTerrainImport[]) => void;
}

export function ImportGpx({
  onImporte,
  onTracesChange,
  onRelevesChange,
}: ImportGpxProps) {
  const { t } = useI18n();
  const [fichiers, setFichiers] = useState<File[]>([]);
  const [enCours, setEnCours] = useState(false);
  const [indexCourant, setIndexCourant] = useState(0);
  const [resultats, setResultats] = useState<ResultatFichier[]>([]);

  const reinitialiser = async (nouveaux: File[]) => {
    setFichiers(nouveaux);
    setResultats([]);
    setIndexCourant(0);
    // Reset les relevés côté parent (on commence un nouveau lot)
    onRelevesChange?.([]);
    // Parse les fichiers en parallèle côté client pour la prévisualisation carte.
    // Les échecs individuels ne bloquent rien : le fichier mal formé sera détecté
    // côté backend lors du POST et reporté dans le tableau d'erreurs.
    const tracesParseees: TraceGpx[] = [];
    await Promise.all(
      nouveaux.map(async (f) => {
        try {
          tracesParseees.push(await parserGpxFichier(f));
        } catch (err) {
          // L'erreur réelle remontera aussi du backend lors de l'import HTTP,
          // mais on la trace dans la console pour pouvoir debug rapidement.
          // eslint-disable-next-line no-console
          console.warn(`[ImportGpx] parse côté client échoué pour ${f.name} :`, err);
        }
      }),
    );
    onTracesChange?.(tracesParseees);
  };

  const importerTout = async () => {
    if (fichiers.length === 0 || enCours) return;
    setEnCours(true);
    setResultats([]);
    setIndexCourant(0);
    const accumulateur: ResultatFichier[] = [];

    for (let i = 0; i < fichiers.length; i++) {
      const fichier = fichiers[i];
      setIndexCourant(i + 1);
      try {
        const reponse = await api.terrainImport(fichier);
        accumulateur.push({ nomFichier: fichier.name, reponse, erreur: null });
        // Rafraîchit le parent dès la première réussite — les graphiques se
        // peuplent au fur et à mesure.
        onImporte?.();
        // Cumule les relevés détectés pour les marqueurs carte
        const cumulReleves = accumulateur.flatMap(
          (r) => r.reponse?.releves ?? [],
        );
        onRelevesChange?.(cumulReleves);
      } catch (e) {
        accumulateur.push({
          nomFichier: fichier.name,
          reponse: null,
          erreur: e instanceof Error ? e.message : String(e),
        });
      }
      setResultats([...accumulateur]);
    }

    setEnCours(false);
  };

  // Stats consolidées
  const stats = useMemo(() => {
    const reussis = resultats.filter((r) => r.reponse !== null);
    const enErreur = resultats.filter((r) => r.erreur !== null);
    const releves = reussis.flatMap((r) =>
      (r.reponse?.releves ?? []).map((rel) => ({
        ...rel,
        nomFichier: r.nomFichier,
      })),
    );
    return {
      nbReussis: reussis.length,
      nbEchecs: enErreur.length,
      nbTronconsDetectes: releves.length,
      releves,
    };
  }, [resultats]);

  const totalFichiers = fichiers.length;
  const progression =
    enCours && totalFichiers > 0
      ? t("fiabilite.progressionLot")
          .replace("{n}", String(indexCourant))
          .replace("{total}", String(totalFichiers))
      : null;

  return (
    <Card titre={t("fiabilite.importTitle")} description={t("fiabilite.importDescription")}>
      {/* Zone de sélection + bouton */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <label className="flex-1">
          <span className="sr-only">{t("fiabilite.choisirFichier")}</span>
          <input
            type="file"
            accept=".gpx,application/gpx+xml"
            multiple
            onChange={(e) =>
              reinitialiser(e.target.files ? Array.from(e.target.files) : [])
            }
            className="block w-full text-fluid-sm text-paa-navy-700 dark:text-paa-blue-100
                       file:mr-3 file:rounded-md file:border-0 file:bg-paa-navy-700 file:px-3
                       file:py-2 file:text-fluid-sm file:font-medium file:text-white
                       file:hover:bg-paa-navy-800 file:cursor-pointer"
          />
        </label>
        <button
          type="button"
          onClick={importerTout}
          disabled={fichiers.length === 0 || enCours}
          className="btn-primary disabled:opacity-50"
        >
          {enCours
            ? (progression ?? t("common.loading"))
            : fichiers.length > 1
              ? t("fiabilite.btnImporterLot").replace(
                  "{n}",
                  String(fichiers.length),
                )
              : t("fiabilite.btnImporter")}
        </button>
      </div>

      {/* Liste des fichiers sélectionnés (avant import) */}
      {fichiers.length > 0 && resultats.length === 0 && (
        <ul className="mt-3 list-disc pl-5 text-fluid-xs app-text-muted">
          {fichiers.slice(0, 10).map((f) => (
            <li key={f.name}>
              {f.name} — {(f.size / 1024).toFixed(0)} ko
            </li>
          ))}
          {fichiers.length > 10 && (
            <li>{t("fiabilite.etPlus").replace("{n}", String(fichiers.length - 10))}</li>
          )}
        </ul>
      )}

      {/* Barre de progression simple */}
      {enCours && totalFichiers > 0 && (
        <div className="mt-3">
          <div className="h-2 w-full overflow-hidden rounded-full bg-paa-blue-100 dark:bg-paa-navy-800">
            <div
              className="h-full bg-paa-navy-700 transition-all"
              style={{ width: `${(indexCourant / totalFichiers) * 100}%` }}
            />
          </div>
          <p className="mt-1 text-fluid-xs app-text-muted">{progression}</p>
        </div>
      )}

      {/* Récap consolidé après import */}
      {resultats.length > 0 && (
        <div className="mt-4 flex flex-col gap-3">
          <div className="grid gap-2 text-fluid-xs sm:grid-cols-3">
            <Info
              label={t("fiabilite.lotFichiersReussis")}
              valeur={`${stats.nbReussis} / ${resultats.length}`}
            />
            <Info
              label={t("fiabilite.lotFichiersErreurs")}
              valeur={String(stats.nbEchecs)}
              alerte={stats.nbEchecs > 0}
            />
            <Info
              label={t("fiabilite.nbTronconsDetectes")}
              valeur={`${stats.nbTronconsDetectes} / 6`}
            />
          </div>

          {/* Erreurs par fichier (le cas échéant) */}
          {stats.nbEchecs > 0 && (
            <ul className="rounded-md border border-statut-congestionne/40 bg-statut-congestionne/10 p-3 text-fluid-xs text-statut-congestionne">
              {resultats
                .filter((r) => r.erreur !== null)
                .map((r) => (
                  <li key={r.nomFichier}>
                    <strong>{r.nomFichier}</strong> — {r.erreur}
                  </li>
                ))}
            </ul>
          )}

          {/* Tableau consolidé des relevés détectés */}
          {stats.releves.length > 0 && (
            <div className="overflow-x-auto">
              <table className="min-w-full text-fluid-xs">
                <thead className="bg-paa-blue-50 dark:bg-paa-navy-800">
                  <tr className="text-left">
                    <Th>{t("fiabilite.colFichier")}</Th>
                    <Th>{t("fiabilite.colTroncon")}</Th>
                    <Th>{t("fiabilite.colTerrain")}</Th>
                    <Th>{t("fiabilite.colApi")}</Th>
                    <Th>ε</Th>
                    <Th>{t("fiabilite.colConfiance")}</Th>
                  </tr>
                </thead>
                <tbody>
                  {stats.releves.map((r, idx) => (
                    <tr
                      key={`${r.id}-${idx}`}
                      className="border-t app-border"
                    >
                      <Td>
                        <span className="font-mono text-fluid-xs app-text-muted">
                          {r.nomFichier}
                        </span>
                      </Td>
                      <Td>{r.troncon_nom}</Td>
                      <Td>{formaterDuree(r.duree_terrain_s)}</Td>
                      <Td>{formaterDuree(r.duree_api_s)}</Td>
                      <Td>{cellEcart(r)}</Td>
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
          )}
        </div>
      )}
    </Card>
  );
}

function cellEcart(r: ReleveTerrainImport) {
  if (r.ecart_relatif === null) return <span className="app-text-muted">—</span>;
  const classe =
    Math.abs(r.ecart_relatif) > 0.15
      ? "text-statut-congestionne font-semibold"
      : "text-statut-fluide";
  return <span className={classe}>{(r.ecart_relatif * 100).toFixed(1)} %</span>;
}

function Info({
  label,
  valeur,
  alerte,
}: {
  label: string;
  valeur: string;
  alerte?: boolean;
}) {
  return (
    <div className="rounded-md border app-border px-3 py-2 app-surface">
      <div className="app-text-muted">{label}</div>
      <div
        className={
          alerte
            ? "font-semibold text-statut-congestionne"
            : "font-semibold text-paa-navy-900 dark:text-paa-blue-100"
        }
      >
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

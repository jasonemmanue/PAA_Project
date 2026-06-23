"use client";

/**
 * Import de segments GPX libres — sous-portions entre landmarks intermédiaires.
 *
 * Contrairement à ImportGpx (qui attend une trace couvrant un tronçon officiel
 * de bout en bout), ce composant accepte n'importe quelle sous-section enregistrée
 * avec BasicAirData GPS Logger ou toute autre app GPS.
 *
 * L'utilisateur peut optionnellement spécifier :
 *   - le tronçon auquel chaque lot appartient (sinon envoyé sans troncon_id)
 *   - la direction (aller / retour / auto)
 *   - un identifiant de session (groupe les fichiers d'une même sortie)
 *
 * Chaque fichier est envoyé séquentiellement à POST /terrain/segments/import.
 * Les résultats s'affichent au fur et à mesure.
 */

import { useMemo, useRef, useState } from "react";

import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import { parserGpxFichier, type TraceGpx } from "@/lib/gpxClient";
import { useI18n } from "@/lib/i18n";
import type { SegmentImporte, Troncon } from "@/lib/types";

interface ResultatFichier {
  nomFichier: string;
  segment: SegmentImporte | null;
  erreur: string | null;
}

interface ImportSegmentsGpxProps {
  troncons: Troncon[];
  onImporte?: () => void;
  /** Appelé dès la sélection de fichiers — fournit les traces parsées pour la carte. */
  onTracesChange?: (traces: TraceGpx[]) => void;
}

function formaterDureeS(s: number): string {
  const mn = Math.floor(s / 60);
  const sec = s % 60;
  return `${mn}:${String(sec).padStart(2, "0")} min`;
}

export function ImportSegmentsGpx({ troncons, onImporte, onTracesChange }: ImportSegmentsGpxProps) {
  const { t } = useI18n();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [fichiers, setFichiers] = useState<File[]>([]);
  const [tronconId, setTronconId] = useState<string>("");
  const [direction, setDirection] = useState<string>("auto");
  const [sessionId, setSessionId] = useState<string>("");
  const [enCours, setEnCours] = useState(false);
  const [indexCourant, setIndexCourant] = useState(0);
  const [resultats, setResultats] = useState<ResultatFichier[]>([]);

  const stats = useMemo(() => {
    const ok = resultats.filter((r) => r.segment !== null);
    const erreurs = resultats.filter((r) => r.erreur !== null);
    const dureeTotal = ok.reduce((acc, r) => acc + (r.segment?.duree_s ?? 0), 0);
    return { nbOk: ok.length, nbErreurs: erreurs.length, dureeTotal };
  }, [resultats]);

  const annuler = () => {
    setFichiers([]);
    setResultats([]);
    if (inputRef.current) inputRef.current.value = "";
    onTracesChange?.([]);
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
        const segment = await api.segmentsImport(fichier, {
          nomSegment: fichier.name.replace(/\.gpx$/i, ""),
          tronconId: tronconId ? Number(tronconId) : undefined,
          direction:
            direction === "auto" ? undefined : (direction as "aller" | "retour"),
          sessionId: sessionId || undefined,
        });
        accumulateur.push({ nomFichier: fichier.name, segment, erreur: null });
        onImporte?.();
      } catch (e) {
        accumulateur.push({
          nomFichier: fichier.name,
          segment: null,
          erreur: e instanceof Error ? e.message : String(e),
        });
      }
      setResultats([...accumulateur]);
    }

    setEnCours(false);
  };

  const progression =
    enCours && fichiers.length > 0
      ? t("segments.progressionLot")
          .replace("{n}", String(indexCourant))
          .replace("{total}", String(fichiers.length))
      : null;

  return (
    <Card
      titre={t("segments.importTitle")}
      description={t("segments.importDescription")}
    >
      {/* Conseil "par lot" */}
      <div className="mb-4 rounded-md border border-paa-blue-300 bg-paa-blue-50 dark:border-paa-navy-600 dark:bg-paa-navy-800 px-4 py-3 text-fluid-xs app-text-muted">
        <strong className="text-paa-navy-800 dark:text-paa-blue-100">
          {t("segments.conseilLotTitre")}
        </strong>{" "}
        {t("segments.conseilLotDetail")}
      </div>

      {/* Métadonnées optionnelles */}
      <div className="grid gap-3 sm:grid-cols-3 mb-4">
        <div className="flex flex-col gap-1">
          <label className="text-fluid-xs font-medium app-text-muted">
            {t("segments.tronconLabel")}
          </label>
          <select
            value={tronconId}
            onChange={(e) => setTronconId(e.target.value)}
            className="rounded-md border app-border bg-white dark:bg-paa-navy-900 px-2 py-1.5 text-fluid-sm text-paa-navy-800 dark:text-paa-blue-100"
          >
            <option value="">{t("segments.tronconAuto")}</option>
            {troncons.map((tr) => (
              <option key={tr.id} value={String(tr.id)}>
                {tr.id}. {tr.nom}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-fluid-xs font-medium app-text-muted">
            {t("segments.directionLabel")}
          </label>
          <select
            value={direction}
            onChange={(e) => setDirection(e.target.value)}
            className="rounded-md border app-border bg-white dark:bg-paa-navy-900 px-2 py-1.5 text-fluid-sm text-paa-navy-800 dark:text-paa-blue-100"
          >
            <option value="auto">{t("segments.directionAuto")}</option>
            <option value="aller">{t("segments.directionAller")}</option>
            <option value="retour">{t("segments.directionRetour")}</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-fluid-xs font-medium app-text-muted">
            {t("segments.sessionLabel")}
          </label>
          <input
            type="text"
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            placeholder={t("segments.sessionPlaceholder")}
            className="rounded-md border app-border bg-white dark:bg-paa-navy-900 px-2 py-1.5 text-fluid-sm text-paa-navy-800 dark:text-paa-blue-100 placeholder:app-text-muted"
          />
        </div>
      </div>

      {/* Sélection fichiers + boutons */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <label className="flex-1">
          <span className="sr-only">{t("segments.choisirFichier")}</span>
          <input
            ref={inputRef}
            type="file"
            accept=".gpx,application/gpx+xml"
            multiple
            onChange={async (e) => {
              const nouveaux = e.target.files ? Array.from(e.target.files) : [];
              setFichiers(nouveaux);
              setResultats([]);
              // Parse immédiatement côté client pour afficher les traces sur la carte
              if (onTracesChange && nouveaux.length > 0) {
                const traces: TraceGpx[] = [];
                await Promise.all(
                  nouveaux.map(async (f) => {
                    try {
                      traces.push(await parserGpxFichier(f));
                    } catch { /* GPX mal formé — ignoré silencieusement */ }
                  }),
                );
                onTracesChange(traces);
              }
            }}
            className="block w-full text-fluid-sm text-paa-navy-700 dark:text-paa-blue-100
                       file:mr-3 file:rounded-md file:border-0 file:bg-paa-navy-700 file:px-3
                       file:py-2 file:text-fluid-sm file:font-medium file:text-white
                       file:hover:bg-paa-navy-800 file:cursor-pointer"
          />
        </label>
        <div className="flex gap-2 shrink-0">
          {fichiers.length > 0 && !enCours && (
            <button
              type="button"
              onClick={annuler}
              className="rounded-md border app-border px-4 py-2 text-fluid-sm font-medium
                         text-paa-navy-700 dark:text-paa-blue-100 hover:bg-paa-blue-50
                         dark:hover:bg-paa-navy-800 transition-colors whitespace-nowrap"
            >
              Annuler
            </button>
          )}
          <button
            type="button"
            onClick={importerTout}
            disabled={fichiers.length === 0 || enCours}
            className="btn-primary disabled:opacity-50 whitespace-nowrap"
          >
            {enCours
              ? (progression ?? t("common.loading"))
              : t("segments.btnImporter").replace("{n}", String(fichiers.length || 1))}
          </button>
        </div>
      </div>

      {/* Liste fichiers sélectionnés */}
      {fichiers.length > 0 && resultats.length === 0 && !enCours && (
        <ul className="mt-3 list-disc pl-5 text-fluid-xs app-text-muted">
          {fichiers.slice(0, 8).map((f) => (
            <li key={f.name}>{f.name}</li>
          ))}
          {fichiers.length > 8 && (
            <li>… et {fichiers.length - 8} autre(s)</li>
          )}
        </ul>
      )}

      {/* Barre de progression */}
      {enCours && fichiers.length > 0 && (
        <div className="mt-3">
          <div className="h-2 w-full overflow-hidden rounded-full bg-paa-blue-100 dark:bg-paa-navy-800">
            <div
              className="h-full bg-paa-navy-700 transition-all"
              style={{ width: `${(indexCourant / fichiers.length) * 100}%` }}
            />
          </div>
          <p className="mt-1 text-fluid-xs app-text-muted">{progression}</p>
        </div>
      )}

      {/* Résultats */}
      {resultats.length > 0 && (
        <div className="mt-4 flex flex-col gap-3">
          {/* Stats résumé */}
          <div className="grid gap-2 text-fluid-xs sm:grid-cols-3">
            <InfoBox label={t("segments.lotReussis")} valeur={`${stats.nbOk} / ${resultats.length}`} />
            <InfoBox label={t("segments.lotErreurs")} valeur={String(stats.nbErreurs)} alerte={stats.nbErreurs > 0} />
            <InfoBox label={t("segments.durTotale")} valeur={stats.dureeTotal > 0 ? formaterDureeS(stats.dureeTotal) : "—"} />
          </div>

          {/* Erreurs */}
          {stats.nbErreurs > 0 && (
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

          {/* Tableau détaillé */}
          {stats.nbOk > 0 && (
            <div className="overflow-x-auto">
              <table className="min-w-full text-fluid-xs">
                <thead className="bg-paa-blue-50 dark:bg-paa-navy-800">
                  <tr className="text-left">
                    <Th>{t("segments.colFichier")}</Th>
                    <Th>{t("segments.colDirection")}</Th>
                    <Th>{t("segments.colDuree")}</Th>
                    <Th>{t("segments.colDistance")}</Th>
                  </tr>
                </thead>
                <tbody>
                  {resultats
                    .filter((r) => r.segment !== null)
                    .map((r, idx) => (
                      <tr key={idx} className="border-t app-border">
                        <Td>
                          <span className="font-mono text-fluid-xs app-text-muted">
                            {r.nomFichier.length > 40
                              ? `…${r.nomFichier.slice(-37)}`
                              : r.nomFichier}
                          </span>
                        </Td>
                        <Td>
                          <DirectionBadge dir={r.segment!.direction} t={t} />
                        </Td>
                        <Td className="font-medium">
                          {formaterDureeS(r.segment!.duree_s)}
                        </Td>
                        <Td>
                          {r.segment!.distance_m
                            ? `${(r.segment!.distance_m / 1000).toFixed(1)} km`
                            : "—"}
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

function DirectionBadge({ dir, t }: { dir: string | null; t: (k: string) => string }) {
  if (!dir) return <span className="app-text-muted">—</span>;
  const isAller = dir === "aller";
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-fluid-xs font-medium ${
        isAller
          ? "bg-paa-blue-100 text-paa-navy-700 dark:bg-paa-navy-700 dark:text-paa-blue-100"
          : "bg-paa-blue-50 text-paa-navy-500 dark:bg-paa-navy-800 dark:text-paa-blue-200"
      }`}
    >
      {isAller ? t("segments.directionAller") : t("segments.directionRetour")}
    </span>
  );
}

function InfoBox({ label, valeur, alerte }: { label: string; valeur: string; alerte?: boolean }) {
  return (
    <div className="rounded-md border app-border px-3 py-2 app-surface">
      <div className="app-text-muted text-fluid-xs">{label}</div>
      <div className={`font-semibold text-fluid-sm ${alerte ? "text-statut-congestionne" : "text-paa-navy-900 dark:text-paa-blue-100"}`}>
        {valeur}
      </div>
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="px-2 py-2 font-medium text-paa-navy-700 dark:text-paa-blue-100">{children}</th>;
}

function Td({ children, className }: { children: React.ReactNode; className?: string }) {
  return <td className={`px-2 py-2 align-middle ${className ?? ""}`}>{children}</td>;
}

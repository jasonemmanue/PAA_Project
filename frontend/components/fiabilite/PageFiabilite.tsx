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

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";

import { CalibrationTable } from "@/components/fiabilite/CalibrationTable";
import { EvolutionEcart } from "@/components/fiabilite/EvolutionEcart";
import { ImportGpx } from "@/components/fiabilite/ImportGpx";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { api } from "@/lib/api";
import { parserGpxFichier, type TraceGpx } from "@/lib/gpxClient";
import { useI18n } from "@/lib/i18n";
import type {
  CalibrationResponse,
  CarteEtat,
  ReleveTerrainImport,
  ReleveTerrainResponse,
  Troncon,
} from "@/lib/types";

// Import dynamique côté client — Leaflet utilise `window` au montage.
const CarteApercu = dynamic(
  () =>
    import("@/components/fiabilite/CarteApercu").then((m) => m.CarteApercu),
  { ssr: false },
);

const FENETRE_CALIBRATION = 4;

export function PageFiabilite() {
  const { t } = useI18n();
  const [troncons, setTroncons] = useState<Troncon[]>([]);
  const [etatCarte, setEtatCarte] = useState<CarteEtat | null>(null);
  const [releves, setReleves] = useState<ReleveTerrainResponse | null>(null);
  const [calibration, setCalibration] = useState<CalibrationResponse | null>(null);
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState<string | null>(null);
  // États dérivés pour la prévisualisation carte (hydratés depuis Railway).
  const [tracesApercu, setTracesApercu] = useState<TraceGpx[]>([]);
  const [relevesApercu, setRelevesApercu] = useState<ReleveTerrainImport[]>([]);

  const rechargerDonnees = useCallback(async () => {
    setChargement(true);
    setErreur(null);
    try {
      const [tr, etc, rel, cal] = await Promise.all([
        api.troncons(),
        api.carteEtat(),
        api.terrainReleves({ limite: 500 }),
        api.terrainCalibration(FENETRE_CALIBRATION),
      ]);
      setTroncons(Array.isArray(tr) ? tr : []);
      setEtatCarte(etc);
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

  /**
   * Hydratation cartographique depuis Railway.
   *
   * Au montage (et après chaque rechargement de releves), on récupère depuis
   * la dernière session terrain :
   *   - Pour chaque fichier GPX unique : on télécharge le `.gpx` brut via
   *     /terrain/releves/{id}/gpx, on le parse côté client → 1 trace par fichier
   *   - Tous les relevés de la session → marqueurs début/fin sur la carte
   *
   * Cette hydratation est complètement déterministe — pas de cache navigateur,
   * pas de localStorage. La source de vérité reste Railway.
   */
  useEffect(() => {
    const lignes = releves?.lignes ?? [];
    if (lignes.length === 0) {
      setTracesApercu([]);
      setRelevesApercu([]);
      return;
    }
    // 1) Identifier la dernière session
    const derniereDate = lignes
      .map((l) => l.date_session)
      .sort()
      .reverse()[0];
    const lignesDerniere = lignes.filter((l) => l.date_session === derniereDate);

    // 2) Un releve_id représentatif par nom de fichier (pour ne télécharger
    //    qu'une fois chaque GPX même si plusieurs tronçons y sont détectés)
    const idParFichier = new Map<string, number>();
    for (const r of lignesDerniere) {
      const cle = r.nom_fichier_gpx ?? `releve_${r.id}`;
      if (!idParFichier.has(cle)) idParFichier.set(cle, r.id);
    }

    // 3) Téléchargement + parse en parallèle
    let annule = false;
    (async () => {
      const traces: TraceGpx[] = [];
      await Promise.all(
        Array.from(idParFichier.entries()).map(async ([nom, id]) => {
          try {
            const fichier = await api.terrainGpx(id);
            const trace = await parserGpxFichier(fichier);
            traces.push({ ...trace, nomFichier: nom });
          } catch (err) {
            // 410 Gone = relevé pré-migration 0005 dont le fichier est perdu
            // sur le disque Railway éphémère. Inutile d'alerter l'utilisateur.
            const statut = (err as { statut?: number })?.statut;
            if (statut === 410) {
              // eslint-disable-next-line no-console
              console.info(
                `[PageFiabilite] relevé ${id} : contenu perdu (pré-migration 0005)`,
              );
            } else {
              // eslint-disable-next-line no-console
              console.warn(
                `[PageFiabilite] téléchargement GPX échoué pour le relevé ${id} :`,
                err,
              );
            }
          }
        }),
      );
      if (annule) return;
      setTracesApercu(traces);
      // Pour les marqueurs : on transforme les releves historiques en
      // ReleveTerrainImport-compatibles (les champs utilisés sont id, troncon_id).
      setRelevesApercu(
        lignesDerniere.map((r) => ({
          id: r.id,
          troncon_id: r.troncon_id,
          troncon_nom: "",
          horodatage_passage_utc: r.horodatage_passage_utc ?? "",
          duree_terrain_s: r.duree_mesuree_s ?? 0,
          duree_api_s: r.duree_api_s,
          ecart_relatif: r.ecart_relatif,
          confiance_matching: r.confiance_matching,
          distance_trace_m: 0,
          distance_officielle_m: 0,
        })),
      );
    })();
    return () => {
      annule = true;
    };
  }, [releves]);

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

      {/* Import GPX (avec callbacks vers la carte) */}
      <ImportGpx
        onImporte={rechargerDonnees}
        onTracesChange={setTracesApercu}
        onRelevesChange={setRelevesApercu}
      />

      {/* Prévisualisation cartographique des traces uploadées */}
      <CarteApercu
        etatCarte={etatCarte}
        traces={tracesApercu}
        releves={relevesApercu}
      />

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

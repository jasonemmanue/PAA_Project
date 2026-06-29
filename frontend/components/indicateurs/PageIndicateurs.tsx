"use client";

/**
 * Page Indicateurs — orchestration des sous-composants.
 *
 * Layout responsive :
 *  - mobile (<768)  : tout empilé verticalement
 *  - tablette       : sélecteurs en ligne, graphiques empilés
 *  - desktop (≥1024): courbe + heatmap côte à côte, évolution en bas
 */

import { useEffect, useState } from "react";

import { BarrePilotage } from "@/components/indicateurs/BarrePilotage";
import { CourbeJournee } from "@/components/indicateurs/CourbeJournee";
import { EvolutionPluriannuelle } from "@/components/indicateurs/EvolutionPluriannuelle";
import { HeatmapHoraire } from "@/components/indicateurs/HeatmapHoraire";
import { KpiCards } from "@/components/indicateurs/KpiCards";
import {
  SelecteurPeriode,
  SelecteurTroncon,
  type Periode,
} from "@/components/indicateurs/Selecteurs";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type {
  IndicateursPeriode,
  SerieTemporelle,
  Troncon,
} from "@/lib/types";

const FENETRES: Record<Periode, number> = {
  "24h": 1,
  "7j": 7,
  "30j": 30,
  "90j": 90,
};

export function PageIndicateurs() {
  const { t } = useI18n();

  const [troncons, setTroncons] = useState<Troncon[]>([]);
  const [tronconId, setTronconId] = useState<number | null>(null);
  const [periode, setPeriode] = useState<Periode>("24h");
  const [indicateurs, setIndicateurs] = useState<IndicateursPeriode | null>(null);
  const [serie, setSerie] = useState<SerieTemporelle | null>(null);
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState<string | null>(null);

  // 1) Charger la liste des tronçons une seule fois
  useEffect(() => {
    let annule = false;
    api
      .troncons()
      .then((list) => {
        if (annule) return;
        const liste = Array.isArray(list) ? list : [];
        setTroncons(liste);
        // Sélectionne le premier tronçon (ou un troncon=ID dans l'URL si fourni)
        const params = new URLSearchParams(window.location.search);
        const fromUrl = Number(params.get("troncon"));
        const idInitial =
          Number.isFinite(fromUrl) && fromUrl > 0
            ? fromUrl
            : liste[0]?.id ?? null;
        setTronconId(idInitial);
      })
      .catch((e) =>
        !annule &&
        setErreur(e instanceof Error ? e.message : String(e)),
      );
    return () => {
      annule = true;
    };
  }, []);

  // 2) Recharger les indicateurs et la série quand le tronçon ou la période changent
  useEffect(() => {
    if (tronconId === null) return;
    let annule = false;
    setChargement(true);
    setErreur(null);

    const fenetre = FENETRES[periode];
    const finDate = new Date();
    const debutDate = new Date();
    debutDate.setDate(finDate.getDate() - fenetre);
    const debut = debutDate.toISOString().slice(0, 10);
    const fin = finDate.toISOString().slice(0, 10);

    Promise.all([
      api.indicateurs(tronconId, periode),
      api.serieTemporelle(tronconId, {
        debut,
        fin,
        granularite: fenetre <= 1 ? "hour" : "day",
      }),
    ])
      .then(([ind, ser]) => {
        if (annule) return;
        setIndicateurs(ind);
        setSerie(ser);
      })
      .catch((e) =>
        !annule && setErreur(e instanceof Error ? e.message : String(e)),
      )
      .finally(() => !annule && setChargement(false));

    return () => {
      annule = true;
    };
  }, [tronconId, periode]);

  return (
    <div className="flex flex-col gap-fluid-4">
      {/* En-tête */}
      <div>
        <h1 className="text-fluid-2xl font-semibold text-paa-navy-900 dark:text-paa-blue-100">
          {t("indicateurs.title")}
        </h1>
        <p className="text-fluid-sm app-text-muted">{t("indicateurs.subtitle")}</p>
      </div>

      {/* Sélecteurs */}
      <div className="flex flex-wrap items-end gap-fluid-4">
        <SelecteurTroncon
          troncons={troncons}
          valeur={tronconId}
          onChange={setTronconId}
        />
        <SelecteurPeriode valeur={periode} onChange={setPeriode} />
      </div>

      {/* Erreur globale */}
      {erreur && (
        <div className="rounded-md bg-statut-congestionne/10 border border-statut-congestionne/40 px-3 py-2 text-fluid-sm text-statut-congestionne">
          {t("common.error")} : {erreur}
        </div>
      )}

      {/* Barre de pilotage : collecte + exports */}
      <BarrePilotage tronconId={tronconId} troncons={troncons} periode={periode} />

      {/* KPIs (temps min/moyen/max + verdict couleur DEESP) */}
      <KpiCards snapshot={indicateurs?.snapshot ?? null} />

      {/* Graphiques principaux : courbe + heatmap côte à côte en desktop */}
      <div className="grid gap-fluid-4 lg:grid-cols-2">
        <CourbeJournee serie={serie} />
        <HeatmapHoraire tronconId={tronconId} />
      </div>

      {/* Évolution pluriannuelle — pleine largeur, filtrée par tronçon sélectionné */}
      <EvolutionPluriannuelle tronconId={tronconId} />

      {/* Indicateur de chargement global discret */}
      {chargement && (
        <div className="text-fluid-xs app-text-muted">{t("common.loading")}</div>
      )}
    </div>
  );
}

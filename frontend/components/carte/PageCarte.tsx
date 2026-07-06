"use client";

/**
 * Page Carte — orchestration : carte Leaflet + panneau liste + légende.
 *
 * Layout :
 *  - desktop (≥ lg) : carte à gauche (2/3), panneau liste à droite (1/3)
 *  - tablette/mobile : carte en haut, panneau dessous (empilés verticalement)
 */

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";

import { LegendeCarte } from "@/components/carte/LegendeCarte";
import { PanneauTroncons } from "@/components/carte/PanneauTroncons";
import { useI18n } from "@/lib/i18n";
import type { CarteEtat } from "@/lib/types";

// La carte Leaflet doit être chargée côté client uniquement
const CarteLeaflet = dynamic(
  () => import("@/components/carte/CarteLeaflet").then((m) => m.CarteLeaflet),
  {
    ssr: false,
    loading: () => (
      <div className="grid h-full place-items-center text-fluid-sm app-text-muted">
        Chargement de la carte…
      </div>
    ),
  },
);

export function PageCarte() {
  const { t, locale } = useI18n();
  const [etat, setEtat] = useState<CarteEtat | null>(null);
  const [selectionId, setSelectionId] = useState<number | null>(null);
  // Sélection d'un sous-tronçon (T1A, T2A…) — cliquable dans le panneau
  // pour zoomer sur sa portion précise de l'axe parent.
  const [selectionSousId, setSelectionSousId] = useState<number | null>(null);

  const handleEtat = useCallback((e: CarteEtat) => setEtat(e), []);
  const handleSelectionner = useCallback((id: number) => {
    setSelectionSousId(null);
    setSelectionId(id);
  }, []);
  const handleSelectionnerSous = useCallback(
    (sousId: number, parentId: number) => {
      // On garde la sélection axe pour la surbrillance, mais la priorité
      // de zoom bascule sur le sous-tronçon.
      setSelectionId(parentId);
      setSelectionSousId(sousId);
    },
    [],
  );

  const sousTitre = (() => {
    if (!etat) return t("carte.subtitle");
    const axes = etat.troncons.filter((tr) => tr.est_axe !== false);
    const nbAxes = axes.length;
    const nbTroncons = axes.reduce(
      (n, tr) => n + (tr.sous_troncons?.length ?? 0),
      0,
    );
    if (locale === "fr") {
      const partAxes = `${nbAxes} axe${nbAxes > 1 ? "s" : ""}`;
      const partTroncons = `${nbTroncons} tronçon${nbTroncons > 1 ? "s" : ""}`;
      const libelle =
        nbTroncons === 0 ? partAxes : `${partAxes} et ${partTroncons}`;
      return `État instantané des ${libelle} surveillés.`;
    }
    const partAxes = `${nbAxes} ax${nbAxes > 1 ? "es" : "is"}`;
    const partTroncons = `${nbTroncons} segment${nbTroncons > 1 ? "s" : ""}`;
    const libelle =
      nbTroncons === 0 ? partAxes : `${partAxes} and ${partTroncons}`;
    return `Real-time snapshot of ${libelle} monitored.`;
  })();

  // Bloquer le scroll de la page — seul le panneau latéral défile
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, []);

  return (
    <div className="flex flex-col gap-fluid-4">
      <div>
        <h1 className="text-fluid-2xl font-semibold text-paa-navy-900 dark:text-paa-blue-100">
          {t("carte.title")}
        </h1>
        <p className="text-fluid-sm app-text-muted">{sousTitre}</p>
      </div>

      <div className="grid gap-fluid-4 lg:grid-cols-3">
        {/* Carte — colonne principale (2/3 sur desktop, pleine largeur sinon) */}
        <div className="paa-card relative h-[55vh] min-h-[360px] overflow-hidden lg:col-span-2 lg:h-[70vh]">
          <CarteLeaflet
            tronconSelectionneId={selectionId}
            sousTronconSelectionneId={selectionSousId}
            onEtatChange={handleEtat}
            onSelectionner={handleSelectionner}
          />
          <LegendeCarte />
        </div>

        {/* Panneau liste — colonne droite scrollable (hauteur calée sur la carte) */}
        <div className="h-[55vh] overflow-y-auto lg:h-[70vh]">
          <PanneauTroncons
            etat={etat}
            selectionId={selectionId}
            selectionSousId={selectionSousId}
            onSelectionner={handleSelectionner}
            onSelectionnerSous={handleSelectionnerSous}
          />
        </div>
      </div>
    </div>
  );
}

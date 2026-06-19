"use client";

/**
 * Page Carte — orchestration : carte Leaflet + panneau liste + légende.
 *
 * Layout :
 *  - desktop (≥ lg) : carte à gauche (2/3), panneau liste à droite (1/3)
 *  - tablette/mobile : carte en haut, panneau dessous (empilés verticalement)
 */

import dynamic from "next/dynamic";
import { useCallback, useState } from "react";

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
  const { t } = useI18n();
  const [etat, setEtat] = useState<CarteEtat | null>(null);
  const [selectionId, setSelectionId] = useState<number | null>(null);

  const handleEtat = useCallback((e: CarteEtat) => setEtat(e), []);
  const handleSelectionner = useCallback((id: number) => setSelectionId(id), []);

  return (
    <div className="flex flex-col gap-fluid-4">
      <div>
        <h1 className="text-fluid-2xl font-semibold text-paa-navy-900 dark:text-paa-blue-100">
          {t("carte.title")}
        </h1>
        <p className="text-fluid-sm app-text-muted">{t("carte.subtitle")}</p>
      </div>

      <div className="grid gap-fluid-4 lg:grid-cols-3">
        {/* Carte — colonne principale (2/3 sur desktop, pleine largeur sinon) */}
        <div className="paa-card relative h-[55vh] min-h-[360px] overflow-hidden lg:col-span-2 lg:h-[70vh]">
          <CarteLeaflet
            tronconSelectionneId={selectionId}
            onEtatChange={handleEtat}
            onSelectionner={handleSelectionner}
          />
          <LegendeCarte />
        </div>

        {/* Panneau liste — colonne droite (1/3 sur desktop) */}
        <div className="flex flex-col gap-fluid-4">
          <PanneauTroncons
            etat={etat}
            selectionId={selectionId}
            onSelectionner={handleSelectionner}
          />
        </div>
      </div>
    </div>
  );
}

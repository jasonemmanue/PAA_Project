"use client";

/**
 * Page Carte — orchestration : carte Leaflet + panneau liste + légende.
 *
 * Layout :
 *  - desktop (≥ lg) : carte à gauche (2/3), panneau liste à droite (1/3)
 *  - tablette/mobile : carte en haut, panneau dessous (empilés verticalement)
 *
 * Le panneau s'ouvre sur l'état des axes, les axes chauds et le tableau des
 * temps de traversée (GET /carte/resume-axes, rafraîchi toutes les 5 min).
 */

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";

import { LegendeCarte } from "@/components/carte/LegendeCarte";
import { PanneauTroncons } from "@/components/carte/PanneauTroncons";
import { api } from "@/lib/api";
import type { CarteEtat, ResumeAxes } from "@/lib/types";

// Fréquence de rafraîchissement du tableau des temps (la collecte est horaire)
const INTERVALLE_RESUME_AXES_MS = 5 * 60 * 1000;

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
  const [etat, setEtat] = useState<CarteEtat | null>(null);
  const [resumeAxes, setResumeAxes] = useState<ResumeAxes | null>(null);
  const [selectionId, setSelectionId] = useState<number | null>(null);
  // Sélection d'un sous-tronçon (T1A, T2A…) — cliquable dans le panneau
  // pour zoomer sur sa portion précise de l'axe parent.
  const [selectionSousId, setSelectionSousId] = useState<number | null>(null);

  // Compteur incrémenté à chaque clic pour forcer le re-trigger de l'effet
  // même quand on reclique sur le même tronçon (ex. aller → retour du même axe).
  const selectionSeqRef = useRef(0);
  const [selectionSeq, setSelectionSeq] = useState(0);

  const handleEtat = useCallback((e: CarteEtat) => setEtat(e), []);
  const handleSelectionner = useCallback((id: number) => {
    setSelectionSousId(null);
    setSelectionId(id);
    selectionSeqRef.current += 1;
    setSelectionSeq(selectionSeqRef.current);
  }, []);
  const handleSelectionnerSous = useCallback(
    (sousId: number, parentId: number) => {
      setSelectionId(parentId);
      setSelectionSousId(sousId);
      selectionSeqRef.current += 1;
      setSelectionSeq(selectionSeqRef.current);
    },
    [],
  );

  // Temps actuel + min/moy/max de tous les axes
  useEffect(() => {
    let actif = true;
    const charger = () => {
      api.resumeAxes()
        .then((r) => { if (actif) setResumeAxes(r); })
        .catch(() => {});
    };
    charger();
    const intervalle = setInterval(charger, INTERVALLE_RESUME_AXES_MS);
    return () => { actif = false; clearInterval(intervalle); };
  }, []);

  // Bloquer le scroll de la page — seul le panneau latéral défile
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, []);

  return (
    <div className="flex flex-col gap-fluid-4">
      <div className="grid gap-fluid-4 lg:grid-cols-3">
        {/* Carte — colonne principale (2/3 sur desktop, pleine largeur sinon) */}
        <div className="paa-card relative h-[55vh] min-h-[360px] overflow-hidden lg:col-span-2 lg:h-[70vh]">
          <CarteLeaflet
            tronconSelectionneId={selectionId}
            sousTronconSelectionneId={selectionSousId}
            selectionSeq={selectionSeq}
            onEtatChange={handleEtat}
            onSelectionner={handleSelectionner}
            onSelectionnerSous={handleSelectionnerSous}
          />
          <LegendeCarte />
        </div>

        {/* Panneau liste — colonne droite scrollable (hauteur calée sur la carte).
            touch-pan-y + overscroll-contain + WebkitOverflowScrolling : contournement
            du bug iOS Safari où overflow-y:auto est bloqué quand body.overflow='hidden'. */}
        <div
          className="h-[55vh] overflow-y-auto touch-pan-y overscroll-contain lg:h-[70vh]"
          style={{ WebkitOverflowScrolling: "touch" } as React.CSSProperties}
        >
          <PanneauTroncons
            etat={etat}
            resumeAxes={resumeAxes}
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

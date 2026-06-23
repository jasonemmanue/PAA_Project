"use client";

/**
 * Page Fiabilité — orchestrateur.
 *
 * Deux blocs principaux :
 *   1. Import segments GPX libres (découpages entre landmarks).
 *   2. Carte de prévisualisation des traces (mise à jour dès la sélection).
 *   3. Résumé précision progressive par tronçon + explications.
 *
 * Le système P5 (import tronçon complet + calibration) a été retiré :
 * les découpages constituent le mode de fonctionnement réel du port.
 * Les indicateurs de calibration seront reconstruits à partir des segments.
 */

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import { ImportSegmentsGpx } from "@/components/fiabilite/ImportSegmentsGpx";
import { ResumeSegmentsBlock } from "@/components/fiabilite/ResumeSegments";
import { PageHeader } from "@/components/ui/PageHeader";
import { api } from "@/lib/api";
import { parserGpxTexte, type TraceGpx } from "@/lib/gpxClient";
import { useI18n } from "@/lib/i18n";
import type { CarteEtat, Troncon } from "@/lib/types";

// Import dynamique côté client — Leaflet utilise `window` au montage.
const CarteApercu = dynamic(
  () =>
    import("@/components/fiabilite/CarteApercu").then((m) => m.CarteApercu),
  { ssr: false },
);

async function chargerTracesDb(): Promise<TraceGpx[]> {
  const liste = await api.segmentsListe();
  if (liste.length === 0) return [];
  const traces: TraceGpx[] = [];
  const TAILLE_LOT = 5;
  for (let i = 0; i < liste.length; i += TAILLE_LOT) {
    const lot = liste.slice(i, i + TAILLE_LOT);
    const resultats = await Promise.allSettled(
      lot.map(async (seg) => {
        const texte = await api.segmentGpxTexte(seg.id);
        return parserGpxTexte(texte, seg.nom_fichier_gpx ?? `segment_${seg.id}.gpx`);
      }),
    );
    for (const r of resultats) {
      if (r.status === "fulfilled") traces.push(r.value);
    }
  }
  return traces;
}

export function PageFiabilite() {
  const { t } = useI18n();
  const [troncons, setTroncons] = useState<Troncon[]>([]);
  const [etatCarte, setEtatCarte] = useState<CarteEtat | null>(null);
  /** Traces persistées en base Railway (chargées au montage + après chaque import). */
  const [tracesDb, setTracesDb] = useState<TraceGpx[]>([]);
  /** Traces des fichiers sélectionnés dans le picker mais pas encore importés. */
  const [tracesSelection, setTracesSelection] = useState<TraceGpx[]>([]);
  const [compteurSegments, setCompteurSegments] = useState(0);

  // Charge tronçons + état carte au premier montage.
  useEffect(() => {
    let actif = true;
    Promise.all([api.troncons(), api.carteEtat()])
      .then(([tr, etc]) => {
        if (!actif) return;
        setTroncons(Array.isArray(tr) ? tr : []);
        setEtatCarte(etc);
      })
      .catch(() => {});
    return () => { actif = false; };
  }, []);

  // Charge/recharge les traces GPX depuis la DB (montage initial + après chaque import).
  useEffect(() => {
    let actif = true;
    chargerTracesDb()
      .then((traces) => { if (actif) setTracesDb(traces); })
      .catch(() => {});
    return () => { actif = false; };
  }, [compteurSegments]);

  // Toutes les traces à afficher = DB + sélection en cours
  const toutesLesTraces = [...tracesDb, ...tracesSelection];

  return (
    <div className="flex flex-col gap-fluid-4">
      <PageHeader
        titre={t("fiabilite.title")}
        sousTitre={t("fiabilite.subtitle")}
      />

      {/* Import segments GPX libres — la sélection de fichiers prévisualise sur la carte */}
      <ImportSegmentsGpx
        troncons={troncons}
        onImporte={() => {
          setCompteurSegments((n) => n + 1);
          setTracesSelection([]); // les nouveaux fichiers sont maintenant en DB
        }}
        onTracesChange={setTracesSelection}
      />

      {/* Carte : traces DB persistées + fichiers sélectionnés en cours */}
      <CarteApercu
        etatCarte={etatCarte}
        traces={toutesLesTraces}
        releves={[]}
      />

      {/* Résumé précision progressive + explications */}
      <ResumeSegmentsBlock rafraichir={compteurSegments} />
    </div>
  );
}

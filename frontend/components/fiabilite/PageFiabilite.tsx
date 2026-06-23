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
import { type TraceGpx } from "@/lib/gpxClient";
import { useI18n } from "@/lib/i18n";
import type { CarteEtat, Troncon } from "@/lib/types";

// Import dynamique côté client — Leaflet utilise `window` au montage.
const CarteApercu = dynamic(
  () =>
    import("@/components/fiabilite/CarteApercu").then((m) => m.CarteApercu),
  { ssr: false },
);

export function PageFiabilite() {
  const { t } = useI18n();
  const [troncons, setTroncons] = useState<Troncon[]>([]);
  const [etatCarte, setEtatCarte] = useState<CarteEtat | null>(null);
  const [tracesApercu, setTracesApercu] = useState<TraceGpx[]>([]);
  const [compteurSegments, setCompteurSegments] = useState(0);

  // Charge uniquement ce dont la page a besoin : liste tronçons + état carte.
  useEffect(() => {
    let actif = true;
    Promise.all([api.troncons(), api.carteEtat()])
      .then(([tr, etc]) => {
        if (!actif) return;
        setTroncons(Array.isArray(tr) ? tr : []);
        setEtatCarte(etc);
      })
      .catch(() => {/* erreur réseau silencieuse — la carte reste vide */});
    return () => { actif = false; };
  }, []);

  return (
    <div className="flex flex-col gap-fluid-4">
      <PageHeader
        titre={t("fiabilite.title")}
        sousTitre={t("fiabilite.subtitle")}
      />

      {/* Import segments GPX libres — la sélection de fichiers met à jour la carte */}
      <ImportSegmentsGpx
        troncons={troncons}
        onImporte={() => setCompteurSegments((n) => n + 1)}
        onTracesChange={setTracesApercu}
      />

      {/* Carte de prévisualisation — traces dès la sélection, même en sous-sections */}
      <CarteApercu
        etatCarte={etatCarte}
        traces={tracesApercu}
        releves={[]}
      />

      {/* Résumé précision progressive + explications */}
      <ResumeSegmentsBlock rafraichir={compteurSegments} />
    </div>
  );
}

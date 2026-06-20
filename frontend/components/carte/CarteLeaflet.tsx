"use client";

/**
 * Composant de carte Leaflet — client uniquement (Leaflet utilise `window`).
 * Affiche les 6 tronçons colorés selon la classe de congestion, met à jour
 * en temps réel via WebSocket, propose des popups détaillés, un recentrage
 * animé et une heatmap des congestions.
 */

import "leaflet/dist/leaflet.css";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Map as LeafletMap, Polyline as LeafletPolyline } from "leaflet";

import { api } from "@/lib/api";
import { decoderPolyline } from "@/lib/polyline";
import {
  couleurClasseCongestion,
  formaterDuree,
  formaterHeureAbidjan,
  libelleClasseCongestion,
  libelleSource,
} from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { CarteEtat, EtatTronconCarte } from "@/lib/types";
import { useWsCarteEtat } from "@/lib/ws";

const TUILE_URL =
  process.env.NEXT_PUBLIC_TILE_URL ??
  "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const TUILE_ATTR =
  process.env.NEXT_PUBLIC_TILE_ATTRIBUTION ?? "&copy; OpenStreetMap contributors";

// Centre approximatif de la zone portuaire d'Abidjan
const CENTRE_ABIDJAN: [number, number] = [5.29, -4.0];
const ZOOM_INITIAL = 12;

type Props = {
  /** Tronçon à mettre en surbrillance et vers lequel zoomer. */
  tronconSelectionneId: number | null;
  /** Callback déclenché lorsque l'état de la carte change (chargement initial ou màj WS). */
  onEtatChange?: (etat: CarteEtat) => void;
  /** Callback de sélection (popup ou clic). */
  onSelectionner?: (tronconId: number) => void;
};

export function CarteLeaflet({
  tronconSelectionneId,
  onEtatChange,
  onSelectionner,
}: Props) {
  const { t, locale } = useI18n();
  const conteneurRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const lignesRef = useRef<Map<number, LeafletPolyline>>(new Map());
  const heatLayerRef = useRef<any>(null);
  const LRef = useRef<typeof import("leaflet") | null>(null);
  const onSelectionnerRef = useRef(onSelectionner);
  onSelectionnerRef.current = onSelectionner;

  const [etat, setEtat] = useState<CarteEtat | null>(null);
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState<string | null>(null);

  // ---- 1. Initialisation Leaflet (une seule fois)
  useEffect(() => {
    let monte = true;
    let nettoyer: (() => void) | null = null;

    (async () => {
      // Import dynamique pour ne pas inclure Leaflet dans le bundle serveur
      const L = (await import("leaflet")).default;
      // leaflet.heat s'enregistre sur L par effet de bord (cf. types/leaflet.heat.d.ts)
      await import("leaflet.heat");
      if (!monte || !conteneurRef.current) return;
      LRef.current = L;

      const map = L.map(conteneurRef.current, {
        center: CENTRE_ABIDJAN,
        zoom: ZOOM_INITIAL,
        zoomControl: true,
        // Bonne ergonomie tactile sur mobile
        tap: true,
        scrollWheelZoom: true,
      });

      L.tileLayer(TUILE_URL, {
        attribution: TUILE_ATTR,
        maxZoom: 19,
      }).addTo(map);

      mapRef.current = map;

      // 1er chargement depuis l'API
      try {
        const initial = await api.carteEtat();
        if (!monte) return;
        setEtat(initial);
        onEtatChange?.(initial);
      } catch (e) {
        if (monte) setErreur(e instanceof Error ? e.message : "Erreur réseau");
      } finally {
        if (monte) setChargement(false);
      }

      nettoyer = () => {
        map.remove();
        mapRef.current = null;
        lignesRef.current.clear();
        heatLayerRef.current = null;
      };
    })();

    return () => {
      monte = false;
      nettoyer?.();
    };
    // onEtatChange est volontairement omis : on s'en sert juste au chargement initial
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- 2. (Re)dessin des polylines et de la heatmap quand l'état change
  useEffect(() => {
    const L = LRef.current;
    const map = mapRef.current;
    if (!L || !map || !etat) return;

    // -- Polylines : si la ligne existe déjà, on actualise sa couleur ; sinon on la crée
    for (const troncon of etat.troncons) {
      const points = pointsTroncon(troncon);
      if (points.length < 2) {
        // Géométrie inutilisable (polyline non décodée + coordonnées manquantes)
        continue;
      }

      const couleur = couleurClasseCongestion(troncon.classe_congestion);
      const existante = lignesRef.current.get(troncon.id);
      if (existante) {
        existante.setLatLngs(points);
        existante.setStyle({ color: couleur, weight: 5, opacity: 0.85 });
      } else {
        const ligne = L.polyline(points, {
          color: couleur,
          weight: 5,
          opacity: 0.85,
          lineCap: "round",
          lineJoin: "round",
        });
        ligne.on("click", () => {
          onSelectionnerRef.current?.(troncon.id);
        });
        ligne.bindPopup(() => construirePopup(troncon, locale), {
          maxWidth: 300,
          className: "paa-popup",
        });
        ligne.addTo(map);
        lignesRef.current.set(troncon.id, ligne);
      }
    }

    // -- Heatmap des congestions : on échantillonne plusieurs points de chaque
    // polyline, pondérés par le TTI (plus le trafic est dense, plus le poids est élevé)
    if (heatLayerRef.current) {
      map.removeLayer(heatLayerRef.current);
      heatLayerRef.current = null;
    }
    const pointsHeat: [number, number, number][] = [];
    for (const troncon of etat.troncons) {
      if (troncon.classe_congestion === "fluide" || troncon.classe_congestion === "indetermine") {
        continue;
      }
      const poids =
        troncon.classe_congestion === "congestionne" ? 1.0 : 0.55;
      const points = pointsTroncon(troncon);
      if (points.length < 2) continue;
      // Échantillonnage 1 point sur 5 pour rester léger
      const pas = Math.max(1, Math.floor(points.length / 8));
      for (let i = 0; i < points.length; i += pas) {
        pointsHeat.push([points[i][0], points[i][1], poids]);
      }
    }
    if (pointsHeat.length > 0) {
      heatLayerRef.current = L.heatLayer(pointsHeat, {
        radius: 28,
        blur: 22,
        maxZoom: 17,
        gradient: { 0.3: "#F39C12", 0.7: "#E67E22", 1.0: "#E74C3C" },
      }).addTo(map);
    }
  }, [etat, locale]);

  // ---- 3. Branchement WebSocket pour les mises à jour temps réel
  const onMessage = useCallback(
    (msg: { type: "snapshot" | "maj"; donnees: CarteEtat }) => {
      setEtat(msg.donnees);
      onEtatChange?.(msg.donnees);
    },
    [onEtatChange],
  );
  const etatWs = useWsCarteEtat(onMessage);

  // ---- 4. Recentrage animé sur sélection
  useEffect(() => {
    const L = LRef.current;
    const map = mapRef.current;
    if (!L || !map || !etat || tronconSelectionneId === null) return;

    const troncon = etat.troncons.find((t) => t.id === tronconSelectionneId);
    if (!troncon) return;

    const points = pointsTroncon(troncon);
    if (points.length >= 2) {
      const bounds = L.latLngBounds(points);
      map.flyToBounds(bounds, { padding: [40, 40], duration: 0.8, maxZoom: 16 });
    }

    const ligne = lignesRef.current.get(tronconSelectionneId);
    ligne?.openPopup();
  }, [tronconSelectionneId, etat]);

  // ---- Indicateur d'état WebSocket
  const libelleEtatWs = useMemo(() => {
    switch (etatWs) {
      case "open":
        return "● temps réel";
      case "connecting":
        return "○ connexion…";
      default:
        return "○ déconnecté";
    }
  }, [etatWs]);

  return (
    <div className="relative h-full w-full">
      <div
        ref={conteneurRef}
        className="h-full w-full"
        aria-label={t("carte.title")}
        role="region"
      />

      {/* Indicateur WS — petit badge en haut à droite de la carte */}
      <div
        className="pointer-events-none absolute right-2 top-2 z-[1000]
                   rounded-md bg-white/90 px-2 py-1 text-fluid-xs font-medium
                   text-paa-navy-900 shadow-paa-sm dark:bg-paa-navy-900/90 dark:text-paa-blue-100"
      >
        {libelleEtatWs}
      </div>

      {chargement && (
        <div className="absolute inset-0 z-[999] flex items-center justify-center bg-white/60 backdrop-blur-sm dark:bg-paa-navy-900/60">
          <span className="rounded-md bg-white px-4 py-2 text-fluid-sm font-medium shadow-paa-md dark:bg-paa-navy-800 dark:text-paa-blue-100">
            {t("common.loading")}
          </span>
        </div>
      )}

      {erreur && !chargement && (
        <div className="absolute inset-x-4 top-4 z-[999] rounded-md bg-statut-congestionne/95 px-3 py-2 text-fluid-sm text-white shadow-paa-md">
          {t("common.error")} : {erreur}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Construction du contenu HTML d'un popup — Leaflet attend une string ou un
// HTMLElement, on retourne une string formatée (le rendu reste léger).
// ---------------------------------------------------------------------------
function construirePopup(t: EtatTronconCarte, locale: "fr" | "en"): string {
  const couleur = couleurClasseCongestion(t.classe_congestion);
  const classe = libelleClasseCongestion(t.classe_congestion, locale);
  const m = t.derniere_mesure;
  const tti = t.tti !== null ? t.tti.toFixed(2) : "—";
  const dureeTrafic = formaterDuree(m?.duree_trafic_s);
  const dureeFluide = formaterDuree(m?.duree_sans_trafic_s);
  const heure = formaterHeureAbidjan(m?.horodatage);
  const sourceLib = libelleSource(m?.source);

  const ficheUrl = `/indicateurs?troncon=${t.id}`;
  const labelFiche = locale === "fr" ? "Voir la fiche détaillée →" : "View details →";
  const labelMesure = locale === "fr" ? "Mesure actuelle" : "Current measurement";
  const labelFluide = locale === "fr" ? "Temps fluide" : "Free-flow time";
  const labelTti = locale === "fr" ? "TTI" : "TTI";
  const labelHeure = locale === "fr" ? "Mesurée à" : "Measured at";
  const labelSource = locale === "fr" ? "Source" : "Source";

  return `
    <div style="font-family: Inter, sans-serif; min-width: 230px;">
      <div style="font-weight: 600; font-size: 14px; color: #0B2545; margin-bottom: 6px;">
        ${escapeHtml(t.nom)}
      </div>
      <div style="display: inline-block; padding: 2px 8px; border-radius: 9999px;
                  background: ${couleur}; color: white; font-size: 12px;
                  font-weight: 600; margin-bottom: 8px;">
        ${escapeHtml(classe)}
      </div>
      <table style="width: 100%; font-size: 12px; color: #1F2937;">
        <tr><td style="padding: 2px 0; color: #6B7280;">${labelMesure}</td><td style="text-align: right; font-weight: 600;">${dureeTrafic}</td></tr>
        <tr><td style="padding: 2px 0; color: #6B7280;">${labelFluide}</td><td style="text-align: right;">${dureeFluide}</td></tr>
        <tr><td style="padding: 2px 0; color: #6B7280;">${labelTti}</td><td style="text-align: right; font-weight: 600;">${tti}</td></tr>
        <tr><td style="padding: 2px 0; color: #6B7280;">${labelHeure}</td><td style="text-align: right;">${heure}</td></tr>
        <tr><td style="padding: 2px 0; color: #6B7280;">${labelSource}</td><td style="text-align: right;">${escapeHtml(sourceLib)}</td></tr>
      </table>
      <a href="${ficheUrl}" style="display: block; margin-top: 8px;
                font-size: 12px; font-weight: 600; color: #1F4E79;
                text-decoration: none;">${labelFiche}</a>
    </div>
  `;
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => {
    switch (c) {
      case "&":
        return "&amp;";
      case "<":
        return "&lt;";
      case ">":
        return "&gt;";
      case '"':
        return "&quot;";
      default:
        return "&#39;";
    }
  });
}

// ---------------------------------------------------------------------------
// Construction défensive de la géométrie d'un tronçon.
// Renvoie un tableau de couples `[lat, lon]` valides. Si rien n'est
// exploitable, renvoie `[]` — l'appelant doit alors ignorer ce tronçon.
//
// Trois sources possibles, dans l'ordre :
//   1. polyline encodée (OSRM) si présente et décodable
//   2. coordonnées origine/destination si elles sont des nombres finis
//   3. rien — on ignore
// ---------------------------------------------------------------------------
function pointsTroncon(t: EtatTronconCarte): [number, number][] {
  // 1) Polyline OSRM
  if (typeof t.polyline === "string" && t.polyline.length > 0) {
    const decodes = decoderPolyline(t.polyline);
    if (decodes.length >= 2 && decodes.every(estCoordonneeValide)) {
      return decodes;
    }
  }
  // 2) Repli : segment droit origine → destination.
  //    Le backend `construire_etat_carte` expose les coords sous `geometrie`,
  //    et certaines versions les ont aussi remontées au top-level.
  const latO = t.lat_origine ?? t.geometrie?.lat_origine ?? NaN;
  const lonO = t.lon_origine ?? t.geometrie?.lon_origine ?? NaN;
  const latD = t.lat_destination ?? t.geometrie?.lat_destination ?? NaN;
  const lonD = t.lon_destination ?? t.geometrie?.lon_destination ?? NaN;
  const segment: [number, number][] = [
    [latO as number, lonO as number],
    [latD as number, lonD as number],
  ];
  if (segment.every(estCoordonneeValide)) {
    return segment;
  }
  // 3) Aucune géométrie utilisable
  return [];
}

function estCoordonneeValide(p: [number, number]): boolean {
  return (
    Array.isArray(p) &&
    typeof p[0] === "number" &&
    typeof p[1] === "number" &&
    Number.isFinite(p[0]) &&
    Number.isFinite(p[1]) &&
    Math.abs(p[0]) <= 90 &&
    Math.abs(p[1]) <= 180
  );
}

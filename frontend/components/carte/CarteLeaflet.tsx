"use client";

/**
 * Composant de carte Leaflet — client uniquement (Leaflet utilise `window`).
 * Affiche tous les tronçons actifs (les 6 officiels + ceux créés via la page
 * Administration) colorés selon la classe de congestion, met à jour en temps
 * réel via WebSocket, propose des popups détaillés, un recentrage animé et
 * une heatmap des congestions.
 */

import "leaflet/dist/leaflet.css";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  Map as LeafletMap,
  Marker as LeafletMarker,
  Polyline as LeafletPolyline,
} from "leaflet";

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
import type { CarteEtat, EtatSousTronconCarte, EtatTronconCarte } from "@/lib/types";
import { useWsCarteEtat } from "@/lib/ws";

const TUILE_URL =
  process.env.NEXT_PUBLIC_TILE_URL ??
  "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const TUILE_ATTR =
  process.env.NEXT_PUBLIC_TILE_ATTRIBUTION ?? "&copy; OpenStreetMap contributors";

// Centre approximatif de la zone portuaire d'Abidjan
const CENTRE_ABIDJAN: [number, number] = [5.29, -4.0];
const ZOOM_INITIAL = 12;

// Classement des classes de congestion pour identifier le « point chaud »
// au chargement (utilisé par le zoom intelligent). Critère DEESP : seul
// "congestionné" est traité comme point chaud.
const ORDRE_GRAVITE: Record<string, number> = {
  congestionne: 2,
  fluide: 1,
  indetermine: 0,
};

// POI — 4 points stratégiques de la zone portuaire. Les libellés correspondent
// à ceux extractibles d'un `troncon.nom` via le séparateur " → " (cf.
// backend/app/sources/coordonnees.py).
const POI_INFO: Record<string, { code: string; libelleCourt: string; couleur: string }> = {
  "CARENA (Plateau)": { code: "C", libelleCourt: "CARENA", couleur: "#1565C8" },
  "Toyota CFAO (Treichville)": { code: "T", libelleCourt: "Toyota CFAO", couleur: "#C62828" },
  "Agence SODECI (Zone 4)": { code: "S", libelleCourt: "SODECI", couleur: "#2E7D32" },
  "Pharmacie Palm Beach": { code: "P", libelleCourt: "Palm Beach", couleur: "#0B2545" },
};

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
  // Polylines des sous-tronçons (clef = "p<parent_id>_s<sous_id>")
  const lignesSousRef = useRef<Map<string, LeafletPolyline>>(new Map());
  const heatLayerRef = useRef<any>(null);
  const LRef = useRef<typeof import("leaflet") | null>(null);
  const onSelectionnerRef = useRef(onSelectionner);
  onSelectionnerRef.current = onSelectionner;
  const poiMarkersRef = useRef<LeafletMarker[]>([]);
  // Garde pour ne déclencher le zoom intelligent qu'une seule fois
  // (sinon la mise à jour WebSocket re-centre toutes les 20 min).
  const zoomInitialFaitRef = useRef(false);

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
        poiMarkersRef.current = [];
        zoomInitialFaitRef.current = false;
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

    // -- Polylines : on dessine chaque tronçon parent. Si le parent a des
    // sous-tronçons, on trace ces derniers avec leur propre couleur DEESP
    // et on dessine le parent en pointillé léger pour la lisibilité de l'axe.
    for (const troncon of etat.troncons) {
      const points = pointsTroncon(troncon);
      if (points.length < 2) continue;

      const aDesSous = (troncon.sous_troncons?.length ?? 0) > 0;
      const couleur = couleurClasseCongestion(troncon.classe_congestion);

      const existante = lignesRef.current.get(troncon.id);
      const style = aDesSous
        ? { color: couleur, weight: 3, opacity: 0.35, dashArray: "6 8" }
        : { color: couleur, weight: 5, opacity: 0.85 };
      if (existante) {
        existante.setLatLngs(points);
        existante.setStyle(style);
      } else {
        const ligne = L.polyline(points, {
          ...style, lineCap: "round", lineJoin: "round",
        });
        ligne.on("click", () => onSelectionnerRef.current?.(troncon.id));
        ligne.bindPopup(() => construirePopup(troncon, locale), {
          maxWidth: 300, className: "paa-popup",
        });
        ligne.addTo(map);
        lignesRef.current.set(troncon.id, ligne);
      }

      // Sous-tronçons — un polyline coloré par sous-tronçon
      for (const sous of troncon.sous_troncons ?? []) {
        const ptsSous = pointsSousTroncon(sous);
        if (ptsSous.length < 2) continue;
        const couleurSous = couleurClasseCongestion(sous.classe_congestion);
        const cle = `p${troncon.id}_s${sous.id}`;
        const existS = lignesSousRef.current.get(cle);
        const styleSous = { color: couleurSous, weight: 6, opacity: 0.95 };
        if (existS) {
          existS.setLatLngs(ptsSous);
          existS.setStyle(styleSous);
        } else {
          const ligneS = L.polyline(ptsSous, {
            ...styleSous, lineCap: "round", lineJoin: "round",
          });
          ligneS.on("click", () => onSelectionnerRef.current?.(troncon.id));
          ligneS.bindPopup(
            () => construirePopupSousTroncon(troncon.nom, sous, locale),
            { maxWidth: 300, className: "paa-popup" },
          );
          ligneS.addTo(map);
          lignesSousRef.current.set(cle, ligneS);
        }
      }
    }

    // Cleanup des sous-tronçons archivés (présents avant mais plus dans l'état)
    const clesActuelles = new Set<string>();
    for (const tr of etat.troncons) {
      for (const s of tr.sous_troncons ?? []) {
        clesActuelles.add(`p${tr.id}_s${s.id}`);
      }
    }
    for (const [cle, ligne] of lignesSousRef.current.entries()) {
      if (!clesActuelles.has(cle)) {
        map.removeLayer(ligne);
        lignesSousRef.current.delete(cle);
      }
    }

    // -- Heatmap des congestions : on échantillonne plusieurs points de chaque
    // polyline congestionnée selon la couleur Google Maps (DEESP). Le poids
    // est proportionnel à la part de rouge sur le tronçon.
    if (heatLayerRef.current) {
      map.removeLayer(heatLayerRef.current);
      heatLayerRef.current = null;
    }
    const pointsHeat: [number, number, number][] = [];
    for (const troncon of etat.troncons) {
      if (troncon.classe_congestion !== "congestionne") {
        // Critère DEESP : on ne signale comme « chaud » que les tronçons
        // qualifiés de congestionnés par les couleurs Google Maps.
        continue;
      }
      // Poids proportionnel à la part de rouge — un tronçon entièrement
      // rouge est plus chaud qu'un tronçon avec quelques % de rouge.
      const pctRouge = troncon.couleur_google?.pourcentage_rouge ?? 0;
      const poids = Math.min(1.0, 0.55 + pctRouge / 100);
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

    // -- POI : 4 markers stratégiques (CARENA, Toyota CFAO, SODECI, Palm Beach)
    //    On collecte les coords uniques en parsant `troncon.nom` (séparateur " → ").
    if (poiMarkersRef.current.length === 0) {
      const poiParLibelle = new Map<string, [number, number]>();
      for (const tr of etat.troncons) {
        const [libO, libD] = tr.nom.split(" → ").map((s) => s.trim());
        const latO = tr.lat_origine ?? tr.geometrie?.lat_origine ?? null;
        const lonO = tr.lon_origine ?? tr.geometrie?.lon_origine ?? null;
        const latD = tr.lat_destination ?? tr.geometrie?.lat_destination ?? null;
        const lonD = tr.lon_destination ?? tr.geometrie?.lon_destination ?? null;
        if (libO && Number.isFinite(latO) && Number.isFinite(lonO)) {
          poiParLibelle.set(libO, [latO as number, lonO as number]);
        }
        if (libD && Number.isFinite(latD) && Number.isFinite(lonD)) {
          poiParLibelle.set(libD, [latD as number, lonD as number]);
        }
      }
      for (const [libelle, [latPt, lonPt]] of poiParLibelle) {
        const info = POI_INFO[libelle];
        if (!info) continue; // libellé inconnu → on ne fabrique pas de POI
        const icone = L.divIcon({
          html: `
            <div class="paa-poi-pin" style="
              background:${info.couleur};
              color:#ffffff;
              border:2px solid #ffffff;
              border-radius:50%;
              width:32px; height:32px;
              display:flex; align-items:center; justify-content:center;
              font-weight:700; font-size:14px;
              box-shadow:0 2px 6px rgba(0,0,0,0.4);
            ">${info.code}</div>`,
          className: "paa-poi-icon",
          iconSize: [32, 32],
          iconAnchor: [16, 16],
        });
        const marker = L.marker([latPt, lonPt], { icon: icone, interactive: true })
          .bindTooltip(info.libelleCourt, {
            direction: "top",
            offset: [0, -10],
            permanent: false,
          })
          .addTo(map);
        poiMarkersRef.current.push(marker);
      }
    }

    // -- Zoom intelligent : au PREMIER chargement, on centre sur le tronçon
    //    le plus dégradé (worst classe DEESP puis % de rouge le plus élevé) ;
    //    si tout est fluide, on cadre sur l'ensemble des tronçons surveillés.
    if (!zoomInitialFaitRef.current && etat.troncons.length > 0) {
      const troncons = etat.troncons.slice();
      troncons.sort((a, b) => {
        const ga = ORDRE_GRAVITE[a.classe_congestion] ?? 0;
        const gb = ORDRE_GRAVITE[b.classe_congestion] ?? 0;
        if (ga !== gb) return gb - ga;
        const ra = a.couleur_google?.pourcentage_rouge ?? 0;
        const rb = b.couleur_google?.pourcentage_rouge ?? 0;
        return rb - ra;
      });
      const cible = troncons[0];
      const points = pointsTroncon(cible);
      if (
        cible.classe_congestion !== "fluide"
        && cible.classe_congestion !== "indetermine"
        && points.length >= 2
      ) {
        const bounds = L.latLngBounds(points);
        map.flyToBounds(bounds, { padding: [40, 40], duration: 1.0, maxZoom: 15 });
      } else {
        // Tout fluide → cadre global sur l'ensemble des tronçons surveillés
        const tousPoints: [number, number][] = [];
        for (const tr of etat.troncons) tousPoints.push(...pointsTroncon(tr));
        if (tousPoints.length >= 2) {
          map.fitBounds(L.latLngBounds(tousPoints), {
            padding: [30, 30],
            maxZoom: 13,
          });
        }
      }
      zoomInitialFaitRef.current = true;
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
  const dureeTrafic = formaterDuree(m?.duree_trafic_s);
  const heure = formaterHeureAbidjan(
    m?.horodatage_local ?? m?.horodatage_utc ?? m?.horodatage,
  );
  const sourceLib = libelleSource(m?.source);

  const pctR = t.couleur_google?.pourcentage_rouge;
  const pctO = t.couleur_google?.pourcentage_orange;
  const pctV = t.couleur_google?.pourcentage_vert;
  const fmtPct = (v: number | null | undefined): string =>
    v !== null && v !== undefined ? `${v.toFixed(1)} %` : "—";

  const ficheUrl = `/indicateurs?troncon=${t.id}`;
  const labelFiche = locale === "fr" ? "Voir la fiche détaillée →" : "View details →";
  const labelMesure = locale === "fr" ? "Temps actuel" : "Current time";
  const labelHeure = locale === "fr" ? "Mesurée à" : "Measured at";
  const labelSource = locale === "fr" ? "Source" : "Source";
  const labelRouge = locale === "fr" ? "🔴 Rouge" : "🔴 Red";
  const labelOrange = locale === "fr" ? "🟠 Orange" : "🟠 Orange";
  const labelVert = locale === "fr" ? "🟢 Vert" : "🟢 Green";
  const motif = t.motif_congestion
    ? `<div style="margin-top: 6px; padding: 6px 8px; background: #F8FAFC;
                  border-left: 3px solid ${couleur}; font-size: 11px;
                  color: #475569; border-radius: 3px;">
         ${escapeHtml(t.motif_congestion)}
       </div>`
    : "";

  return `
    <div style="font-family: Inter, sans-serif; min-width: 240px;">
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
        <tr><td style="padding: 2px 0; color: #6B7280;">${labelRouge}</td><td style="text-align: right; font-weight: 600; color: #E74C3C;">${fmtPct(pctR)}</td></tr>
        <tr><td style="padding: 2px 0; color: #6B7280;">${labelOrange}</td><td style="text-align: right; font-weight: 600; color: #F39C12;">${fmtPct(pctO)}</td></tr>
        <tr><td style="padding: 2px 0; color: #6B7280;">${labelVert}</td><td style="text-align: right; font-weight: 600; color: #2ECC71;">${fmtPct(pctV)}</td></tr>
        <tr><td style="padding: 2px 0; color: #6B7280;">${labelHeure}</td><td style="text-align: right;">${heure}</td></tr>
        <tr><td style="padding: 2px 0; color: #6B7280;">${labelSource}</td><td style="text-align: right;">${escapeHtml(sourceLib)}</td></tr>
      </table>
      ${motif}
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

// ---------------------------------------------------------------------------
// Helpers sous-tronçons
// ---------------------------------------------------------------------------
function pointsSousTroncon(s: EtatSousTronconCarte): [number, number][] {
  if (typeof s.polyline === "string" && s.polyline.length > 0) {
    const decodes = decoderPolyline(s.polyline);
    if (decodes.length >= 2 && decodes.every(estCoordonneeValide)) return decodes;
  }
  const latD = s.geometrie?.lat_debut ?? NaN;
  const lonD = s.geometrie?.lon_debut ?? NaN;
  const latF = s.geometrie?.lat_fin ?? NaN;
  const lonF = s.geometrie?.lon_fin ?? NaN;
  const segment: [number, number][] = [
    [latD as number, lonD as number],
    [latF as number, lonF as number],
  ];
  return segment.every(estCoordonneeValide) ? segment : [];
}

function construirePopupSousTroncon(
  nomParent: string,
  s: EtatSousTronconCarte,
  locale: "fr" | "en",
): string {
  const couleur = s.couleur_etat;
  const libelle = s.libelle_classe ?? s.classe_congestion;
  const km = s.distance_km ?? (s.distance_m ? Math.round(s.distance_m / 10) / 100 : null);
  const tempsRef = s.temps_reference_50kmh_s
    ? Math.round(s.temps_reference_50kmh_s / 60)
    : null;
  const tempsObs = s.derniere_mesure?.duree_trafic_s
    ? Math.round(s.derniere_mesure.duree_trafic_s / 60)
    : null;
  const motif = s.motif_congestion ? `<div class="text-xs opacity-80 mt-1">${s.motif_congestion}</div>` : "";
  const labelTempsRef = locale === "fr" ? "Référence 50 km/h" : "Reference 50 km/h";
  const labelTempsObs = locale === "fr" ? "Temps actuel" : "Current time";
  return `
    <div class="font-sans">
      <div class="text-xs opacity-70">${nomParent}</div>
      <div class="font-bold text-base">${s.code} — ${s.nom_court}</div>
      <div class="mt-1 inline-block px-2 py-0.5 rounded text-white text-xs" style="background:${couleur}">${libelle}</div>
      ${motif}
      <div class="mt-2 text-xs">
        ${km !== null ? `${km} km · ` : ""}
        ${tempsRef !== null ? `${labelTempsRef} : ${tempsRef} min` : ""}
      </div>
      ${tempsObs !== null ? `<div class="text-xs">${labelTempsObs} : <strong>${tempsObs} min</strong></div>` : ""}
    </div>
  `;
}

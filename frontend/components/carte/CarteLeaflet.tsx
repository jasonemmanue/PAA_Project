"use client";

/**
 * Composant de carte Leaflet — client uniquement (Leaflet utilise `window`).
 * Affiche tous les tronçons actifs (les 6 officiels + ceux créés via la page
 * Administration) colorés selon la classe de congestion, met à jour en temps
 * réel via WebSocket, propose un recentrage animé et une heatmap des
 * congestions.
 *
 * Sélection (axe ou tronçon) : pas de popup Leaflet — il s'ouvrait sur le
 * tracé et le masquait. Les informations s'affichent dans une fiche fixe
 * (`FicheSelection`) dont le zoom réserve la place, et le tracé sélectionné
 * est renforcé (halo blanc + trait épaissi, autres axes estompés).
 */

import "leaflet/dist/leaflet.css";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  CircleMarker as LeafletCircle,
  Map as LeafletMap,
  Marker as LeafletMarker,
  Polyline as LeafletPolyline,
} from "leaflet";

import { FicheSelection } from "@/components/carte/FicheSelection";
import { api } from "@/lib/api";
import { decoderPolyline } from "@/lib/polyline";
import { ACCUEIL_AXES_SEULS, couleurClasseCongestion } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { CarteEtat, EtatSousTronconCarte, EtatTronconCarte, IncidentCarte } from "@/lib/types";
import { useWsCarteEtat } from "@/lib/ws";

const TUILE_URL =
  process.env.NEXT_PUBLIC_TILE_URL ??
  "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const TUILE_ATTR =
  process.env.NEXT_PUBLIC_TILE_ATTRIBUTION ?? "&copy; OpenStreetMap contributors";

const SATELLITE_URL =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const SATELLITE_ATTR =
  "Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community";

// Centre approximatif de la zone portuaire d'Abidjan
const CENTRE_ABIDJAN: [number, number] = [5.29, -4.0];
const ZOOM_INITIAL = 12;

// Classement des classes de congestion pour identifier l'axe le plus chaud
// au chargement (utilisé par le zoom intelligent).
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
  /** Tronçon (axe) à mettre en surbrillance et vers lequel zoomer. */
  tronconSelectionneId: number | null;
  /** Sous-tronçon (T1A, T2A…) à mettre en surbrillance et vers lequel zoomer.
   *  Prioritaire sur `tronconSelectionneId` pour le zoom quand défini. */
  sousTronconSelectionneId?: number | null;
  /** Compteur incrémenté à chaque clic pour forcer le re-trigger de l'effet
   *  même quand on reclique sur le même tronçon. */
  selectionSeq?: number;
  /** Callback déclenché lorsque l'état de la carte change (chargement initial ou màj WS). */
  onEtatChange?: (etat: CarteEtat) => void;
  /** Callback de sélection (popup ou clic). */
  onSelectionner?: (tronconId: number) => void;
  /** Callback de sélection d'un sous-tronçon (clic sur sa polyline). */
  onSelectionnerSous?: (sousId: number, parentId: number) => void;
};

export function CarteLeaflet({
  tronconSelectionneId,
  sousTronconSelectionneId = null,
  selectionSeq = 0,
  onEtatChange,
  onSelectionner,
  onSelectionnerSous,
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
  const onSelectionnerSousRef = useRef(onSelectionnerSous);
  onSelectionnerSousRef.current = onSelectionnerSous;
  const poiMarkersRef = useRef<LeafletMarker[]>([]);
  // CircleMarkers des incidents actifs (mis à jour à chaque changement d'état)
  const incidentMarkersRef = useRef<any[]>([]);
  // Marqueurs début (vert) et fin (rouge) du tronçon sélectionné
  const markerDebutSelRef = useRef<LeafletCircle | null>(null);
  const markerFinSelRef = useRef<LeafletCircle | null>(null);
  // Style de base de chaque polyline (restauré quand la sélection change)
  const styleBaseRef = useRef<Map<LeafletPolyline, { color: string; weight: number; opacity: number }>>(new Map());
  // Halo blanc sous le tracé sélectionné
  const haloRef = useRef<LeafletPolyline | null>(null);
  // Garde pour ne déclencher le zoom intelligent qu'une seule fois
  // (sinon la mise à jour WebSocket re-centre toutes les 20 min).
  const zoomInitialFaitRef = useRef(false);

  const [etat, setEtat] = useState<CarteEtat | null>(null);
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState<string | null>(null);
  const [satellite, setSatellite] = useState(false);
  // Fiche de sélection masquée par l'utilisateur (réaffichée au clic suivant)
  const [ficheFermee, setFicheFermee] = useState(false);
  // Fiche compacte (bas, pleine largeur) sur les cartes étroites
  const [ficheCompacte, setFicheCompacte] = useState(false);
  const tileLayerRef = useRef<any>(null);

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

      tileLayerRef.current = L.tileLayer(TUILE_URL, {
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

  // ---- Bascule fond de carte OSM ↔ Satellite
  useEffect(() => {
    const L = LRef.current;
    const map = mapRef.current;
    if (!L || !map) return;
    if (tileLayerRef.current) {
      tileLayerRef.current.remove();
    }
    if (satellite) {
      tileLayerRef.current = L.tileLayer(SATELLITE_URL, {
        attribution: SATELLITE_ATTR,
        maxZoom: 19,
      }).addTo(map);
    } else {
      tileLayerRef.current = L.tileLayer(TUILE_URL, {
        attribution: TUILE_ATTR,
        maxZoom: 19,
      }).addTo(map);
    }
  }, [satellite]);

  // ---- 2. (Re)dessin des polylines et de la heatmap quand l'état change
  useEffect(() => {
    const L = LRef.current;
    const map = mapRef.current;
    if (!L || !map || !etat) return;

    // -- Polylines : on dessine chaque tronçon parent en trait plein visible.
    // Si le parent a des sous-tronçons, ils se superposent au-dessus en plus
    // épais (rendu couche par couche). Le parent reste tracé sur toute sa
    // longueur — c'est important quand les sous-tronçons ne couvrent qu'une
    // fraction de l'axe (cf. T1A = 1.5 km sur 11.9 km).
    for (const troncon of etat.troncons) {
      const points = pointsTroncon(troncon);
      if (points.length < 2) continue;

      const aDesSous = (troncon.sous_troncons?.length ?? 0) > 0;
      // Mode axes seuls : couleur de la classe d'axe (≥ 50 % de distance congestionnée).
      // Sinon, axes avec sous-tronçons : couleur de base (les tronçons portent la congestion),
      // axes sans sous-tronçons : couleur selon la classe DEESP.
      const couleur = ACCUEIL_AXES_SEULS
        ? couleurClasseCongestion(troncon.classe_axe ?? troncon.classe_congestion ?? "indetermine")
        : aDesSous
          ? (troncon.couleur_etat || "#1F4E79")
          : couleurClasseCongestion(troncon.classe_congestion ?? "indetermine");

      const existante = lignesRef.current.get(troncon.id);
      const style = { color: couleur, weight: 6, opacity: 0.95 };
      if (existante) {
        existante.setLatLngs(points);
        existante.setStyle(style);
        styleBaseRef.current.set(existante, style);
      } else {
        const ligne = L.polyline(points, {
          ...style, lineCap: "round", lineJoin: "round",
        });
        ligne.on("click", (e: L.LeafletMouseEvent) => {
          // En cas de superposition (axe + sous-tronçon), on remonte la
          // polyline cliquée au-dessus pour que SA couleur soit visible.
          L.DomEvent.stopPropagation(e);
          ligne.bringToFront();
          onSelectionnerRef.current?.(troncon.id);
        });
        ligne.addTo(map);
        lignesRef.current.set(troncon.id, ligne);
        styleBaseRef.current.set(ligne, style);
      }

      // Sous-tronçons — un polyline coloré par sous-tronçon (aucun en mode axes seuls)
      for (const sous of ACCUEIL_AXES_SEULS ? [] : troncon.sous_troncons ?? []) {
        const ptsSous = pointsSousTroncon(sous);
        if (ptsSous.length < 2) continue;
        const couleurSous = couleurClasseCongestion(sous.classe_congestion);
        const cle = `p${troncon.id}_s${sous.id}`;
        const existS = lignesSousRef.current.get(cle);
        const styleSous = { color: couleurSous, weight: 6, opacity: 0.95 };
        if (existS) {
          existS.setLatLngs(ptsSous);
          existS.setStyle(styleSous);
          styleBaseRef.current.set(existS, styleSous);
        } else {
          const ligneS = L.polyline(ptsSous, {
            ...styleSous, lineCap: "round", lineJoin: "round",
          });
          ligneS.on("click", (e: L.LeafletMouseEvent) => {
            L.DomEvent.stopPropagation(e);
            ligneS.bringToFront();
            onSelectionnerSousRef.current?.(sous.id, troncon.id);
          });
          ligneS.addTo(map);
          lignesSousRef.current.set(cle, ligneS);
          styleBaseRef.current.set(ligneS, styleSous);
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
        styleBaseRef.current.delete(ligne);
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
    // Critère DEESP : seuls les tracés qualifiés « congestionné » par les
    // couleurs Google Maps chauffent. Poids proportionnel à la part de rouge.
    const ajouterChaleur = (points: [number, number][], pctRouge: number) => {
      if (points.length < 2) return;
      const poids = Math.min(1.0, 0.55 + pctRouge / 100);
      const pas = Math.max(1, Math.floor(points.length / 8));
      for (let i = 0; i < points.length; i += pas) {
        pointsHeat.push([points[i][0], points[i][1], poids]);
      }
    };
    for (const troncon of etat.troncons) {
      if (troncon.classe_congestion === "congestionne") {
        ajouterChaleur(pointsTroncon(troncon), troncon.couleur_google?.pourcentage_rouge ?? 0);
      }
      for (const sous of troncon.sous_troncons ?? []) {
        if (sous.classe_congestion === "congestionne") {
          ajouterChaleur(pointsSousTroncon(sous), sous.couleur_google?.pourcentage_rouge ?? 0);
        }
      }
    }
    if (pointsHeat.length > 0) {
      heatLayerRef.current = L.heatLayer(pointsHeat, {
        radius: 28,
        blur: 22,
        maxZoom: 17,
        // Nappe strictement dans la famille rouge de la légende
        // (congestionné = #E74C3C) — pas d'orange qui polluerait la lecture.
        gradient: { 0.3: "#FCA5A5", 0.7: "#E74C3C", 1.0: "#B71C1C" },
      }).addTo(map);
    }

    // -- Incidents actifs géolocalisés : CircleMarker coloré par sévérité
    for (const cm of incidentMarkersRef.current) map.removeLayer(cm);
    incidentMarkersRef.current = [];
    for (const inc of etat.incidents_actifs ?? []) {
      const couleur = couleurSeveriteIncident(inc.severite);
      const age = Date.now() - new Date(inc.horodatage_publication).getTime();
      const actif = age < 30 * 24 * 60 * 60 * 1000;
      const cm = L.circleMarker([inc.lat, inc.lon], {
        radius: 10,
        color: "#fff",
        weight: 2,
        fillColor: couleur,
        fillOpacity: actif ? 0.9 : 0.35,
        interactive: true,
        bubblingMouseEvents: false,
        pane: "markerPane",
      });
      cm.bindPopup(construirePopupIncident(inc, locale), {
        maxWidth: 280,
        className: "paa-popup",
      });
      cm.addTo(map);
      incidentMarkersRef.current.push(cm);
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

    // -- Zoom intelligent : au PREMIER chargement, on centre sur l'axe le plus
    //    chaud (classe d'axe puis part de distance congestionnée) ; si aucun
    //    axe n'est congestionné, on cadre sur l'ensemble des axes surveillés.
    if (!zoomInitialFaitRef.current && etat.troncons.length > 0) {
      const classeAxe = (tr: EtatTronconCarte) => tr.classe_axe ?? tr.classe_congestion ?? "indetermine";
      const troncons = etat.troncons.slice();
      troncons.sort((a, b) => {
        const ga = ORDRE_GRAVITE[classeAxe(a)] ?? 0;
        const gb = ORDRE_GRAVITE[classeAxe(b)] ?? 0;
        if (ga !== gb) return gb - ga;
        return (b.pct_distance_congestionnee ?? 0) - (a.pct_distance_congestionnee ?? 0);
      });
      const cible = troncons[0];
      const points = pointsTroncon(cible);
      if (classeAxe(cible) === "congestionne" && points.length >= 2) {
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

  // ---- 4. Sélection : zoom (place réservée à la fiche), marqueurs début/fin,
  //         mise en valeur du tracé. Aucun popup : la fiche ne masque rien.
  useEffect(() => {
    const L = LRef.current;
    const map = mapRef.current;

    // Nettoyage de la sélection précédente
    markerDebutSelRef.current?.remove();
    markerDebutSelRef.current = null;
    markerFinSelRef.current?.remove();
    markerFinSelRef.current = null;
    haloRef.current?.remove();
    haloRef.current = null;
    for (const [ligne, style] of styleBaseRef.current) ligne.setStyle(style);

    if (!L || !map || !etat || tronconSelectionneId === null) return;

    const axe = etat.troncons.find((t) => t.id === tronconSelectionneId);
    if (!axe) return;
    const sous = sousTronconSelectionneId !== null
      ? (axe.sous_troncons ?? []).find((s) => s.id === sousTronconSelectionneId) ?? null
      : null;

    // Réserve la place de la fiche : bas de carte (étroit) ou droite (large)
    const largeur = conteneurRef.current?.clientWidth ?? 800;
    const hauteur = conteneurRef.current?.clientHeight ?? 500;
    const compacte = largeur < 640;
    setFicheCompacte(compacte);
    setFicheFermee(false);
    const optionsZoom = compacte
      ? { paddingTopLeft: [30, 50] as [number, number], paddingBottomRight: [30, Math.round(hauteur * 0.45) + 20] as [number, number] }
      : { paddingTopLeft: [50, 50] as [number, number], paddingBottomRight: [320, 40] as [number, number] };

    const pointsSelection = sous ? pointsSousTroncon(sous) : pointsTroncon(axe);
    if (pointsSelection.length >= 2) {
      map.flyToBounds(L.latLngBounds(pointsSelection), {
        ...optionsZoom,
        duration: 0.8,
        maxZoom: sous ? 17 : 16,
      });

      // Mise en valeur : autres axes estompés, halo blanc sous la sélection
      const estDeLaSelection = (ligne: LeafletPolyline) =>
        ligne === lignesRef.current.get(axe.id)
        || [...lignesSousRef.current.entries()].some(
          ([cle, l]) => l === ligne && cle.startsWith(`p${axe.id}_s`),
        );
      for (const [ligne, style] of styleBaseRef.current) {
        if (!estDeLaSelection(ligne)) ligne.setStyle({ ...style, opacity: 0.3 });
      }
      haloRef.current = L.polyline(pointsSelection, {
        color: "#ffffff",
        weight: 15,
        opacity: 0.95,
        lineCap: "round",
        lineJoin: "round",
        interactive: false,
      }).addTo(map);

      const ligneAxe = lignesRef.current.get(axe.id);
      if (sous) {
        ligneAxe?.bringToFront();
        haloRef.current.bringToFront();
        const ligneSous = lignesSousRef.current.get(`p${axe.id}_s${sous.id}`);
        const base = ligneSous ? styleBaseRef.current.get(ligneSous) : undefined;
        if (ligneSous && base) {
          ligneSous.setStyle({ ...base, weight: 10, opacity: 1 });
          ligneSous.bringToFront();
        }
      } else {
        haloRef.current.bringToFront();
        const base = ligneAxe ? styleBaseRef.current.get(ligneAxe) : undefined;
        if (ligneAxe && base) {
          ligneAxe.setStyle({ ...base, weight: 9, opacity: 1 });
          ligneAxe.bringToFront();
        }
        // Les tronçons codifiés de l'axe restent visibles au-dessus de lui
        for (const s of axe.sous_troncons ?? []) {
          const l = lignesSousRef.current.get(`p${axe.id}_s${s.id}`);
          const b = l ? styleBaseRef.current.get(l) : undefined;
          if (l && b) {
            l.setStyle({ ...b, weight: 9, opacity: 1 });
            l.bringToFront();
          }
        }
      }
    }

    // Marqueurs DÉBUT (vert) et FIN (rouge) dans le sens de circulation
    const debut = sous
      ? (sous.sens === "inverse"
        ? [sous.geometrie?.lat_fin, sous.geometrie?.lon_fin]
        : [sous.geometrie?.lat_debut, sous.geometrie?.lon_debut])
      : [axe.lat_origine ?? axe.geometrie?.lat_origine, axe.lon_origine ?? axe.geometrie?.lon_origine];
    const fin = sous
      ? (sous.sens === "inverse"
        ? [sous.geometrie?.lat_debut, sous.geometrie?.lon_debut]
        : [sous.geometrie?.lat_fin, sous.geometrie?.lon_fin])
      : [axe.lat_destination ?? axe.geometrie?.lat_destination, axe.lon_destination ?? axe.geometrie?.lon_destination];
    const libelleDebut = sous
      ? `🟢 ${t("carte.fiche.debut")} ${sous.code} : ${sous.nom_court}`
      : `🟢 ${t("carte.fiche.depart")} : ${axe.origine_libelle ?? axe.nom}`;
    const libelleFin = sous
      ? `🔴 ${t("carte.fiche.fin")} ${sous.code} : ${sous.nom_court}`
      : `🔴 ${t("carte.fiche.arrivee")} : ${axe.destination_libelle ?? axe.nom}`;
    const poserMarqueur = (coords: (number | null | undefined)[], couleur: string, libelle: string) => {
      const [lat, lon] = coords;
      if (lat == null || lon == null || !Number.isFinite(lat) || !Number.isFinite(lon)) return null;
      return L.circleMarker([lat, lon], {
        radius: 11,
        color: "#ffffff",
        fillColor: couleur,
        fillOpacity: 1,
        weight: 3,
        pane: "markerPane",
      })
        .bindTooltip(libelle, { direction: "top", permanent: false })
        .addTo(map);
    };
    markerDebutSelRef.current = poserMarqueur(debut, "#16a34a", libelleDebut);
    markerFinSelRef.current = poserMarqueur(fin, "#dc2626", libelleFin);
    // t n'est utilisé que pour les infobulles : pas de re-zoom au changement de langue
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tronconSelectionneId, sousTronconSelectionneId, selectionSeq, etat]);

  // Objets affichés dans la fiche de sélection
  const axeSelectionne = etat && tronconSelectionneId !== null
    ? etat.troncons.find((tr) => tr.id === tronconSelectionneId) ?? null
    : null;
  const sousSelectionne = axeSelectionne && sousTronconSelectionneId !== null
    ? (axeSelectionne.sous_troncons ?? []).find((s) => s.id === sousTronconSelectionneId) ?? null
    : null;

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

      {/* Bouton vue satellite — en haut à gauche, au-dessus du cadran temps réel */}
      <button
        onClick={() => setSatellite((v) => !v)}
        title={satellite ? "Basculer en vue OSM" : "Basculer en vue satellite"}
        className="absolute left-14 top-2 z-[1050] flex items-center gap-1.5 rounded-md
                   bg-white/95 px-2.5 py-1.5 text-fluid-xs font-semibold shadow-paa-sm
                   border border-gray-200 hover:bg-paa-blue-50 transition-colors
                   dark:bg-paa-navy-800/95 dark:border-paa-navy-600 dark:text-paa-blue-100 dark:hover:bg-paa-navy-700"
      >
        {satellite ? (
          <>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5" aria-hidden><path fillRule="evenodd" d="M9.293 2.293a1 1 0 0 1 1.414 0l7 7A1 1 0 0 1 17 11h-1v6a1 1 0 0 1-1 1h-2a1 1 0 0 1-1-1v-3a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v3a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-6H3a1 1 0 0 1-.707-1.707l7-7Z" clipRule="evenodd" /></svg>
            OSM
          </>
        ) : (
          <>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5" aria-hidden><path d="M4.464 3.162A2 2 0 0 1 6.28 2h7.44a2 2 0 0 1 1.816 1.162l1.154 2.5c.067.145.115.291.145.438A3.508 3.508 0 0 0 16 6H4c-.288 0-.568.035-.835.1.03-.147.078-.293.145-.438l1.154-2.5Z" /><path fillRule="evenodd" d="M2 9.5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6Zm3.72 3.47a.75.75 0 0 1 1.06 0l.47.47V10.5a.75.75 0 0 1 1.5 0v2.94l.47-.47a.75.75 0 1 1 1.06 1.06l-1.72 1.72a.75.75 0 0 1-1.06 0l-1.72-1.72a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" /></svg>
            Satellite
          </>
        )}
      </button>

      {/* Indicateur WS — petit badge en haut à droite de la carte.
          z-[1050] : au-dessus des contrôles Leaflet internes (z-1000 isolés)
          mais bien en dessous de la topbar (z-1100) et du drawer (z-1200). */}
      <div
        className="pointer-events-none absolute right-2 top-2 z-[1050]
                   rounded-md bg-white/90 px-2 py-1 text-fluid-xs font-medium
                   text-paa-navy-900 shadow-paa-sm dark:bg-paa-navy-900/90 dark:text-paa-blue-100"
      >
        {libelleEtatWs}
      </div>

      {axeSelectionne && !ficheFermee && (
        <FicheSelection
          axe={axeSelectionne}
          sous={sousSelectionne}
          compacte={ficheCompacte}
          onFermer={() => setFicheFermee(true)}
        />
      )}

      {chargement && (
        <div className="absolute inset-0 z-[1050] flex items-center justify-center bg-white/60 backdrop-blur-sm dark:bg-paa-navy-900/60">
          <span className="rounded-md bg-white px-4 py-2 text-fluid-sm font-medium shadow-paa-md dark:bg-paa-navy-800 dark:text-paa-blue-100">
            {t("common.loading")}
          </span>
        </div>
      )}

      {erreur && !chargement && (
        <div className="absolute inset-x-4 top-4 z-[1050] rounded-md bg-statut-congestionne/95 px-3 py-2 text-fluid-sm text-white shadow-paa-md">
          {t("common.error")} : {erreur}
        </div>
      )}
    </div>
  );
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

// ---------------------------------------------------------------------------
// Incidents — couleur par sévérité + popup
// ---------------------------------------------------------------------------
function couleurSeveriteIncident(severite: string | null): string {
  switch (severite) {
    case "grave":   return "#dc2626";
    case "moyen":   return "#f97316";
    case "mineur":  return "#eab308";
    default:        return "#6b7280";
  }
}

function construirePopupIncident(inc: IncidentCarte, locale: "fr" | "en"): string {
  const couleur = couleurSeveriteIncident(inc.severite);
  const age = Date.now() - new Date(inc.horodatage_publication).getTime();
  const heures = Math.floor(age / 3_600_000);
  const minutes = Math.floor((age % 3_600_000) / 60_000);
  const ageStr = heures > 0
    ? locale === "fr" ? `il y a ${heures}h${minutes > 0 ? `${minutes}min` : ""}` : `${heures}h${minutes > 0 ? `${minutes}min` : ""} ago`
    : locale === "fr" ? `il y a ${minutes} min` : `${minutes} min ago`;
  const labelType: Record<string, string> = {
    accident: locale === "fr" ? "Accident" : "Accident",
    embouteillage: locale === "fr" ? "Embouteillage" : "Traffic jam",
    route_barree: locale === "fr" ? "Route barrée" : "Road closed",
    travaux: locale === "fr" ? "Travaux" : "Roadworks",
    autre: locale === "fr" ? "Autre" : "Other",
  };
  const type = inc.type_incident ? (labelType[inc.type_incident] ?? inc.type_incident) : "—";
  const labelSev: Record<string, string> = {
    grave: locale === "fr" ? "Grave" : "Severe",
    moyen: locale === "fr" ? "Modéré" : "Moderate",
    mineur: locale === "fr" ? "Mineur" : "Minor",
    inconnu: locale === "fr" ? "Inconnu" : "Unknown",
  };
  const sev = inc.severite ? (labelSev[inc.severite] ?? inc.severite) : "—";
  return `
    <div style="font-family:Inter,sans-serif;min-width:220px;">
      <div style="display:inline-block;padding:2px 8px;border-radius:9999px;
                  background:${couleur};color:white;font-size:11px;font-weight:600;
                  margin-bottom:6px;">${escapeHtml(type)} — ${escapeHtml(sev)}</div>
      <div style="font-weight:600;font-size:13px;color:#0B2545;margin-bottom:4px;">
        ${escapeHtml(inc.titre)}
      </div>
      <div style="font-size:11px;color:#6B7280;">${ageStr}</div>
    </div>
  `;
}

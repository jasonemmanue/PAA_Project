"use client";

/**
 * Carte d'aperçu pour la page Fiabilité.
 *
 * Affiche :
 *   - Fond OpenStreetMap (mêmes tuiles que la page Carte principale).
 *   - Les 6 polylines officielles des tronçons (en référence, fines).
 *   - 1..N traces GPX uploadées (parsées côté client) en surcouche, couleur
 *     dorée bien visible.
 *   - Des marqueurs verts au début et rouges à la fin de chaque segment
 *     **détecté** par le backend (issus de `releves.horodatage_passage_utc`).
 *
 * NB : la spec P5 demande la « prévisualisation de la trace recalée ». Comme
 * OSRM Match n'est pas exposé sur Railway (cf. CLAUDE.md § 8.3), on affiche
 * la **trace brute** du GPX. Pour avoir la trace recalée, il faudrait soit
 * exposer OSRM en prod, soit renvoyer la polyline recalée depuis le backend
 * dans la réponse `/terrain/import` (extension future).
 */

import "leaflet/dist/leaflet.css";

import { useEffect, useMemo, useRef, useState } from "react";
import type {
  Layer as LeafletLayer,
  Map as LeafletMap,
  Polyline as LeafletPolyline,
} from "leaflet";

import { Card } from "@/components/ui/Card";
import { decoderPolyline } from "@/lib/polyline";
import type { TraceGpx } from "@/lib/gpxClient";
import { useI18n } from "@/lib/i18n";
import type { CarteEtat, ReleveTerrainImport } from "@/lib/types";

const TUILE_URL =
  process.env.NEXT_PUBLIC_TILE_URL ??
  "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const TUILE_ATTR =
  process.env.NEXT_PUBLIC_TILE_ATTRIBUTION ?? "&copy; OpenStreetMap contributors";

const CENTRE_ABIDJAN: [number, number] = [5.29, -4.0];
const ZOOM_INITIAL = 12;

// Palette pour les traces — 6 couleurs distinctes, contrastées sur OSM.
// L'or reste l'identité visuelle principale ; les autres servent à distinguer
// les traces lorsque plusieurs sont superposées.
const PALETTE_TRACES = [
  "#FFB300", // ambre
  "#D81B60", // rose vif
  "#5E35B1", // violet
  "#00897B", // turquoise
  "#3949AB", // indigo
  "#F4511E", // orange profond
];
const COULEUR_MARQUEUR_DEBUT = "#2ECC71";
const COULEUR_MARQUEUR_FIN = "#E74C3C";

type Props = {
  /** État de la carte (mêmes polylines + couleurs que la page Carte). */
  etatCarte: CarteEtat | null;
  /** Traces GPX parsées côté client. */
  traces: TraceGpx[];
  /** Relevés produits par l'import (pour placer les marqueurs début/fin). */
  releves: ReleveTerrainImport[];
};

export function CarteApercu({ etatCarte, traces, releves }: Props) {
  const { t } = useI18n();
  const conteneurRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const LRef = useRef<typeof import("leaflet") | null>(null);
  const polylinesTroncons = useRef<LeafletPolyline[]>([]);
  const polylinesTraces = useRef<LeafletPolyline[]>([]);
  const marqueurs = useRef<LeafletLayer[]>([]);
  const [pret, setPret] = useState(false);

  // 1) Initialisation Leaflet (une seule fois)
  useEffect(() => {
    let monte = true;
    (async () => {
      const L = (await import("leaflet")).default;
      if (!monte || !conteneurRef.current) return;
      LRef.current = L;
      const map = L.map(conteneurRef.current, {
        center: CENTRE_ABIDJAN,
        zoom: ZOOM_INITIAL,
        scrollWheelZoom: true,
      });
      L.tileLayer(TUILE_URL, { attribution: TUILE_ATTR, maxZoom: 19 }).addTo(map);
      mapRef.current = map;
      setPret(true);
    })();
    return () => {
      monte = false;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  // 2) Affichage de tous les tronçons surveillés (référence) — recalculé quand l'état carte change
  useEffect(() => {
    const L = LRef.current;
    const map = mapRef.current;
    if (!pret || !L || !map || !etatCarte) return;

    polylinesTroncons.current.forEach((p) => p.remove());
    polylinesTroncons.current = [];

    for (const tr of etatCarte.troncons) {
      try {
        // Les coordonnées peuvent venir soit du top-level (rétro-compat) soit
        // du sous-objet `geometrie` (forme actuelle du backend).
        const latO = tr.lat_origine ?? tr.geometrie?.lat_origine ?? null;
        const lonO = tr.lon_origine ?? tr.geometrie?.lon_origine ?? null;
        const latD = tr.lat_destination ?? tr.geometrie?.lat_destination ?? null;
        const lonD = tr.lon_destination ?? tr.geometrie?.lon_destination ?? null;

        let coords: [number, number][] = [];
        if (typeof tr.polyline === "string" && tr.polyline.length > 0) {
          try {
            coords = decoderPolyline(tr.polyline);
          } catch {
            coords = [];
          }
        }
        // Repli sur les extrémités si la polyline est absente ou invalide
        if (
          coords.length < 2
          && Number.isFinite(latO)
          && Number.isFinite(lonO)
          && Number.isFinite(latD)
          && Number.isFinite(lonD)
        ) {
          coords = [
            [latO as number, lonO as number],
            [latD as number, lonD as number],
          ];
        }
        // On ne dessine QUE si on a une liste non-vide de paires finies
        const coordsValides = coords.filter(
          (pt) =>
            Array.isArray(pt)
            && pt.length === 2
            && Number.isFinite(pt[0])
            && Number.isFinite(pt[1]),
        );
        if (coordsValides.length < 2) continue;

        const ligne = L.polyline(coordsValides, {
          color: tr.couleur_etat ?? "#888",
          weight: 3,
          opacity: 0.6,
          dashArray: "6 6",
        });
        ligne.addTo(map);
        ligne.bindTooltip(tr.nom, { sticky: true });
        polylinesTroncons.current.push(ligne);

        // Sous-tronçons : lignes pleines, plus épaisses, colorées par classe DEESP.
        for (const sous of tr.sous_troncons ?? []) {
          let coordsSous: [number, number][] = [];
          if (typeof sous.polyline === "string" && sous.polyline.length > 0) {
            try {
              coordsSous = decoderPolyline(sous.polyline);
            } catch {
              coordsSous = [];
            }
          }
          if (coordsSous.length < 2) {
            const latS = sous.geometrie?.lat_debut ?? null;
            const lonS = sous.geometrie?.lon_debut ?? null;
            const latF = sous.geometrie?.lat_fin ?? null;
            const lonF = sous.geometrie?.lon_fin ?? null;
            if (
              Number.isFinite(latS) && Number.isFinite(lonS)
              && Number.isFinite(latF) && Number.isFinite(lonF)
            ) {
              coordsSous = [
                [latS as number, lonS as number],
                [latF as number, lonF as number],
              ];
            }
          }
          const coordsSousValides = coordsSous.filter(
            (pt) => Array.isArray(pt) && pt.length === 2
              && Number.isFinite(pt[0]) && Number.isFinite(pt[1]),
          );
          if (coordsSousValides.length < 2) continue;

          const ligneSous = L.polyline(coordsSousValides, {
            color: sous.couleur_etat ?? "#888",
            weight: 5,
            opacity: 0.9,
          });
          ligneSous.addTo(map);
          ligneSous.bindTooltip(
            `${sous.code} — ${sous.nom_court}`,
            { sticky: true },
          );
          polylinesTroncons.current.push(ligneSous);
        }
      } catch (err) {
        // Un tronçon mal formé ne doit pas faire planter toute la carte
        // eslint-disable-next-line no-console
        console.warn(
          `[CarteApercu] tronçon id=${tr?.id} non dessiné :`,
          err,
        );
      }
    }
  }, [pret, etatCarte]);

  // 3) Affichage des traces GPX uploadées
  useEffect(() => {
    const L = LRef.current;
    const map = mapRef.current;
    if (!pret || !L || !map) return;

    polylinesTraces.current.forEach((p) => p.remove());
    polylinesTraces.current = [];

    const bounds: [number, number][] = [];
    for (let i = 0; i < traces.length; i++) {
      const trace = traces[i];
      try {
        if (!trace || !Array.isArray(trace.points)) continue;
        const coords = trace.points
          .filter((p) => p && Number.isFinite(p.lat) && Number.isFinite(p.lon))
          .map((p) => [p.lat, p.lon] as [number, number]);
        if (coords.length < 2) continue;
        bounds.push(...coords);
        const couleur = PALETTE_TRACES[i % PALETTE_TRACES.length];
        const ligne = L.polyline(coords, {
          color: couleur,
          weight: 5,
          opacity: 0.75,
        });
        ligne.addTo(map);
        ligne.bindTooltip(trace.nomFichier, { sticky: true });
        polylinesTraces.current.push(ligne);
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn(
          `[CarteApercu] trace ${trace?.nomFichier} non dessinée :`,
          err,
        );
      }
    }

    if (bounds.length >= 2) {
      try {
        map.fitBounds(bounds as any, { padding: [30, 30], maxZoom: 14 });
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn("[CarteApercu] fitBounds a échoué :", err);
      }
    }
  }, [pret, traces]);

  // 4) Marqueurs début/fin des segments détectés
  useEffect(() => {
    const L = LRef.current;
    const map = mapRef.current;
    if (!pret || !L || !map || !etatCarte) return;

    marqueurs.current.forEach((m) => m.remove());
    marqueurs.current = [];

    const tronconsParId = new Map(etatCarte.troncons.map((tr) => [tr.id, tr]));

    // Dédup par LIBELLÉ DE POI (et non par coord) : SODECI et Toyota CFAO
    // sont à 600 m l'un de l'autre — un dédup par coord arrondie les sépare
    // bien en théorie, mais à zoom 12 leurs markers de 28 px se chevauchent
    // visuellement. Dédupliquer par libellé garantit qu'on dessine UN
    // marker logique par POI, à sa coord exacte (celle du troncon dont il
    // est origine ou destination). On compte sur troncon_id unique pour
    // éviter de double-compter quand une session contient plusieurs relevés
    // pour le même tronçon.
    interface PoiInfo {
      libelle: string;
      lat: number;
      lon: number;
      departs: Set<string>;    // troncons "Origine → Destination" qui partent
      arrivees: Set<string>;   // troncons qui arrivent
    }
    const poiParLibelle = new Map<string, PoiInfo>();

    const ajouter = (
      libelle: string,
      lat: number,
      lon: number,
      role: "depart" | "arrivee",
      tronconNom: string,
    ) => {
      const existant = poiParLibelle.get(libelle);
      const info = existant ?? {
        libelle, lat, lon,
        departs: new Set<string>(),
        arrivees: new Set<string>(),
      };
      if (role === "depart") info.departs.add(tronconNom);
      else info.arrivees.add(tronconNom);
      poiParLibelle.set(libelle, info);
    };

    for (const releve of releves) {
      const tr = tronconsParId.get(releve.troncon_id);
      if (!tr) continue;
      const latO = tr.lat_origine ?? tr.geometrie?.lat_origine ?? null;
      const lonO = tr.lon_origine ?? tr.geometrie?.lon_origine ?? null;
      const latD = tr.lat_destination ?? tr.geometrie?.lat_destination ?? null;
      const lonD = tr.lon_destination ?? tr.geometrie?.lon_destination ?? null;
      const [libO, libD] = tr.nom.split(" → ").map((s) => s.trim());
      if (libO && Number.isFinite(latO) && Number.isFinite(lonO)) {
        ajouter(libO, latO as number, lonO as number, "depart", tr.nom);
      }
      if (libD && Number.isFinite(latD) && Number.isFinite(lonD)) {
        ajouter(libD, latD as number, lonD as number, "arrivee", tr.nom);
      }
    }

    const boundsMarqueurs: [number, number][] = [];

    const fabriquerBadge = (
      couleur: string,
      symbole: string,
      compte: number,
      anchorX: number,
    ) => {
      const taille = 34; // un peu plus grand pour faciliter le hover
      return L.divIcon({
        html: `
          <div style="
            background:${couleur};
            color:#ffffff;
            border:3px solid #ffffff;
            border-radius:50%;
            width:${taille}px;
            height:${taille}px;
            display:flex; align-items:center; justify-content:center;
            font-weight:700; font-size:15px;
            box-shadow:0 2px 8px rgba(0,0,0,0.5);
            line-height:1;
            cursor: pointer;
          ">${compte > 1 ? compte : symbole}</div>`,
        className: "paa-poi-fiabilite",
        iconSize: [taille, taille],
        iconAnchor: [anchorX, taille / 2],
      });
    };

    for (const info of poiParLibelle.values()) {
      try {
        const nbDeparts = info.departs.size;
        const nbArrivees = info.arrivees.size;
        // Vert (départs) — décalé vers la gauche pour ne pas couvrir le rouge.
        // zIndexOffset=1000 garantit que le marker passe AU-DESSUS des
        // polylines (dont le tooltip aurait sinon priorité au hover).
        if (nbDeparts > 0) {
          const icone = fabriquerBadge(
            COULEUR_MARQUEUR_DEBUT,
            "↗",
            nbDeparts,
            34, // anchorX = largeur → décale le centre du marker à GAUCHE du point
          );
          const tronconsTexte = Array.from(info.departs).join("<br/>");
          const marker = L.marker([info.lat, info.lon], {
            icon: icone,
            zIndexOffset: 1000,
            riseOnHover: true,
          })
            .bindTooltip(
              `<strong>${t("fiabilite.marqueurDebut")} — ${info.libelle}</strong><br/>${tronconsTexte}`,
              { direction: "top", offset: [0, -18] },
            )
            .addTo(map);
          marqueurs.current.push(marker);
        }
        // Rouge (arrivées) — décalé vers la droite.
        if (nbArrivees > 0) {
          const icone = fabriquerBadge(
            COULEUR_MARQUEUR_FIN,
            "↘",
            nbArrivees,
            0, // anchorX = 0 → décale le centre à DROITE du point
          );
          const tronconsTexte = Array.from(info.arrivees).join("<br/>");
          const marker = L.marker([info.lat, info.lon], {
            icon: icone,
            zIndexOffset: 1000,
            riseOnHover: true,
          })
            .bindTooltip(
              `<strong>${t("fiabilite.marqueurFin")} — ${info.libelle}</strong><br/>${tronconsTexte}`,
              { direction: "top", offset: [0, -18] },
            )
            .addTo(map);
          marqueurs.current.push(marker);
        }
        boundsMarqueurs.push([info.lat, info.lon]);
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn("[CarteApercu] POI non dessiné :", err);
      }
    }

    // Re-centrage incluant les marqueurs pour qu'aucun ne soit hors de la
    // fenêtre (cas typique : Palm Beach au sud, CARENA au nord — la trace
    // seule peut ne pas suffire à cadrer les deux extrémités).
    if (boundsMarqueurs.length >= 2) {
      try {
        map.fitBounds(boundsMarqueurs as any, {
          padding: [50, 50],
          maxZoom: 13,
        });
      } catch {
        /* silencieux */
      }
    }
  }, [pret, etatCarte, releves, t]);

  const aDesContenus = useMemo(
    () => traces.some((t) => t.points.length >= 2),
    [traces],
  );

  return (
    <Card
      titre={t("fiabilite.apercuTitle")}
      description={t("fiabilite.apercuDescription")}
    >
      <div className="relative h-80 w-full overflow-hidden rounded-md sm:h-96 lg:h-[28rem]">
        <div ref={conteneurRef} className="absolute inset-0" />
        {!aDesContenus && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-fluid-sm app-text-muted">
            {t("fiabilite.apercuPlaceholder")}
          </div>
        )}
      </div>
      <p className="mt-2 flex flex-wrap gap-3 text-fluid-xs app-text-muted">
        <span className="inline-flex items-center gap-1">
          <span
            className="inline-block h-2 w-4 rounded-sm"
            style={{
              background: `linear-gradient(90deg, ${PALETTE_TRACES.join(", ")})`,
            }}
          />
          {t("fiabilite.legendeTrace")}
        </span>
        <span className="inline-flex items-center gap-1">
          <span
            className="inline-block h-2 w-4 rounded-sm border border-dashed"
            style={{ borderColor: "#888" }}
          />
          {t("fiabilite.legendeTroncons")}
        </span>
        <span className="inline-flex items-center gap-1">
          <span
            className="inline-block h-3 w-3 rounded-full"
            style={{ backgroundColor: COULEUR_MARQUEUR_DEBUT }}
          />
          {t("fiabilite.marqueurDebut")}
        </span>
        <span className="inline-flex items-center gap-1">
          <span
            className="inline-block h-3 w-3 rounded-full"
            style={{ backgroundColor: COULEUR_MARQUEUR_FIN }}
          />
          {t("fiabilite.marqueurFin")}
        </span>
      </p>
    </Card>
  );
}

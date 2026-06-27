"use client";

/**
 * Carte interactive pour la page Administration (P6.4).
 *
 * Le composant parent contrôle :
 *   - `pointActif` ("debut" | "fin" | null) — quel marker placer au clic
 *   - `onClick` callback déclenché quand l'utilisateur clique
 *   - `debut`, `fin` les coords actuelles à afficher (markers verts/rouges)
 *   - `polylinesParent` les polylines à afficher en arrière-plan (référence)
 *
 * La carte se recentre automatiquement quand `debut` ou `fin` changent.
 */

import "leaflet/dist/leaflet.css";

import { useEffect, useRef } from "react";
import type {
  CircleMarker as LeafletCircle,
  Map as LeafletMap,
  Polyline as LeafletPolyline,
} from "leaflet";

import { decoderPolyline } from "@/lib/polyline";

const CENTRE_ABIDJAN: [number, number] = [5.29, -4.0];
const ZOOM_INITIAL = 12;
const TUILE_URL =
  process.env.NEXT_PUBLIC_TILE_URL ??
  "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";

interface PolylineParent {
  id: number;
  polyline: string | null;
  couleur: string;
  lat_origine?: number | null;
  lon_origine?: number | null;
  lat_destination?: number | null;
  lon_destination?: number | null;
  nom?: string;
}

interface Props {
  pointActif: "debut" | "fin" | null;
  debut: { lat: number; lon: number } | null;
  fin: { lat: number; lon: number } | null;
  polylinesParent?: PolylineParent[];
  onClick: (lat: number, lon: number) => void;
}

export function CarteAdmin({
  pointActif,
  debut,
  fin,
  polylinesParent,
  onClick,
}: Props) {
  const conteneurRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const LRef = useRef<typeof import("leaflet") | null>(null);
  const markerDebutRef = useRef<LeafletCircle | null>(null);
  const markerFinRef = useRef<LeafletCircle | null>(null);
  const lignePreviewRef = useRef<LeafletPolyline | null>(null);
  const polylinesParentsRefs = useRef<LeafletPolyline[]>([]);
  const markersParentRefs = useRef<LeafletCircle[]>([]);
  const onClickRef = useRef(onClick);
  onClickRef.current = onClick;

  // Init Leaflet une seule fois
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
      L.tileLayer(TUILE_URL, {
        attribution: "&copy; OpenStreetMap contributors",
        maxZoom: 19,
      }).addTo(map);
      map.on("click", (e: any) => {
        onClickRef.current?.(e.latlng.lat, e.latlng.lng);
      });
      mapRef.current = map;
    })();
    return () => {
      monte = false;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  // Curseur cliquable selon pointActif
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const el = map.getContainer();
    el.style.cursor = pointActif ? "crosshair" : "";
  }, [pointActif]);

  // Polylines tronçons parents + marqueurs d'extrémité (référence en arrière-plan)
  useEffect(() => {
    const L = LRef.current;
    const map = mapRef.current;
    if (!L || !map) return;

    // Nettoyer les anciens tracés et marqueurs parents
    polylinesParentsRefs.current.forEach((p) => p.remove());
    polylinesParentsRefs.current = [];
    markersParentRefs.current.forEach((m) => m.remove());
    markersParentRefs.current = [];

    for (const t of polylinesParent ?? []) {
      // Tracé de l'axe parent — épais, bien visible, semi-transparent
      if (t.polyline) {
        try {
          const coords = decoderPolyline(t.polyline);
          if (coords.length >= 2) {
            const ligne = L.polyline(coords, {
              color: t.couleur,
              weight: 6,
              opacity: 0.75,
              dashArray: undefined,
            })
              .bindTooltip(t.nom ?? `Axe parent`, {
                sticky: true,
                direction: "top",
                className: "leaflet-tooltip-paa",
              })
              .addTo(map);
            polylinesParentsRefs.current.push(ligne);
          }
        } catch {
          /* polyline invalide → on saute */
        }
      }

      // Marqueur DÉBUT de l'axe parent (vert foncé avec libellé)
      if (t.lat_origine != null && t.lon_origine != null) {
        const m = L.circleMarker([t.lat_origine, t.lon_origine], {
          radius: 9,
          color: "#ffffff",
          fillColor: "#16a34a",
          fillOpacity: 1,
          weight: 3,
        })
          .bindTooltip(`Début axe${t.nom ? ` : ${t.nom}` : ""}`, {
            direction: "top",
            permanent: false,
          })
          .addTo(map);
        markersParentRefs.current.push(m);
      }

      // Marqueur FIN de l'axe parent (rouge foncé avec libellé)
      if (t.lat_destination != null && t.lon_destination != null) {
        const m = L.circleMarker([t.lat_destination, t.lon_destination], {
          radius: 9,
          color: "#ffffff",
          fillColor: "#dc2626",
          fillOpacity: 1,
          weight: 3,
        })
          .bindTooltip(`Fin axe${t.nom ? ` : ${t.nom}` : ""}`, {
            direction: "top",
            permanent: false,
          })
          .addTo(map);
        markersParentRefs.current.push(m);
      }
    }

    // Recadrer la vue sur l'ensemble des parents si au moins un tracé existe
    const tousLesPoints = polylinesParentsRefs.current.flatMap((p) =>
      (p.getLatLngs() as [number, number][]).flat()
    );
    if (tousLesPoints.length > 0) {
      try {
        const bounds = L.latLngBounds(
          polylinesParentsRefs.current.map((p) => p.getBounds()).reduce((acc, b) => acc.extend(b))
        );
        map.fitBounds(bounds, { padding: [30, 30], maxZoom: 14 });
      } catch {
        /* ignore si bounds invalide */
      }
    }
  }, [polylinesParent]);

  // Marker début (vert)
  useEffect(() => {
    const L = LRef.current;
    const map = mapRef.current;
    if (!L || !map) return;
    markerDebutRef.current?.remove();
    markerDebutRef.current = null;
    if (debut) {
      markerDebutRef.current = L.circleMarker([debut.lat, debut.lon], {
        radius: 10,
        color: "#ffffff",
        fillColor: "#2ECC71",
        fillOpacity: 0.95,
        weight: 3,
      })
        .bindTooltip("Début", { direction: "top" })
        .addTo(map);
    }
  }, [debut]);

  // Marker fin (rouge)
  useEffect(() => {
    const L = LRef.current;
    const map = mapRef.current;
    if (!L || !map) return;
    markerFinRef.current?.remove();
    markerFinRef.current = null;
    if (fin) {
      markerFinRef.current = L.circleMarker([fin.lat, fin.lon], {
        radius: 10,
        color: "#ffffff",
        fillColor: "#E74C3C",
        fillOpacity: 0.95,
        weight: 3,
      })
        .bindTooltip("Fin", { direction: "top" })
        .addTo(map);
    }
  }, [fin]);

  // Ligne de prévisualisation entre début et fin
  useEffect(() => {
    const L = LRef.current;
    const map = mapRef.current;
    if (!L || !map) return;
    lignePreviewRef.current?.remove();
    lignePreviewRef.current = null;
    if (debut && fin) {
      const coords: [number, number][] = [
        [debut.lat, debut.lon],
        [fin.lat, fin.lon],
      ];
      lignePreviewRef.current = L.polyline(coords, {
        color: "#9C27B0",
        weight: 4,
        opacity: 0.7,
        dashArray: "8 4",
      }).addTo(map);
      // Recentrer pour englober les deux points
      try {
        map.fitBounds(L.latLngBounds(coords), {
          padding: [40, 40],
          maxZoom: 15,
        });
      } catch {
        /* ignore */
      }
    } else if (debut) {
      map.setView([debut.lat, debut.lon], 14);
    }
  }, [debut, fin]);

  return (
    <div className="relative h-80 w-full overflow-hidden rounded-md sm:h-96">
      <div ref={conteneurRef} className="absolute inset-0" />
      {pointActif && (
        <div className="pointer-events-none absolute left-2 top-2 z-[1000] rounded-md bg-paa-navy-700/95 px-3 py-1.5 text-xs font-medium text-white shadow-paa-md">
          Cliquez sur la carte pour placer le point{" "}
          <strong>{pointActif === "debut" ? "DÉBUT" : "FIN"}</strong>
        </div>
      )}
    </div>
  );
}

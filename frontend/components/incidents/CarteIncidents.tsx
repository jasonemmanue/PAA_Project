"use client";

import "leaflet/dist/leaflet.css";

import { useEffect, useRef, useState } from "react";
import type { Map as LeafletMap, TileLayer as LeafletTile } from "leaflet";

import type { Incident } from "@/lib/types";
import { useI18n } from "@/lib/i18n";

// Centre de la zone portuaire d'Abidjan
const CENTRE: [number, number] = [5.29, -4.0];
const ZOOM = 13;

const TUILE_URL =
  process.env.NEXT_PUBLIC_TILE_URL ??
  "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const TUILE_ATTR =
  process.env.NEXT_PUBLIC_TILE_ATTRIBUTION ?? "&copy; OpenStreetMap contributors";

// Couleur du marker selon la sévérité
function couleurSeverite(severite: string | null): string {
  switch (severite) {
    case "grave":  return "#dc2626"; // rouge
    case "moyen":  return "#f97316"; // orange
    case "mineur": return "#eab308"; // jaune
    default:       return "#6b7280"; // gris
  }
}

interface Props {
  incidents: Incident[];
}

export function CarteIncidents({ incidents }: Props) {
  const { t } = useI18n();
  const conteneurRef = useRef<HTMLDivElement>(null);
  const carteRef = useRef<LeafletMap | null>(null);
  const [pret, setPret] = useState(false);
  const [satellite, setSatellite] = useState(false);
  const tileLayerRef = useRef<any>(null);
  const LRef = useRef<typeof import("leaflet") | null>(null);

  // Initialisation Leaflet côté client uniquement
  useEffect(() => {
    if (typeof window === "undefined" || carteRef.current) return;

    import("leaflet").then((L) => {
      if (!conteneurRef.current || carteRef.current) return;

      const carte = L.map(conteneurRef.current, {
        center: CENTRE,
        zoom: ZOOM,
        zoomControl: true,
      });

      tileLayerRef.current = L.tileLayer(TUILE_URL, { attribution: TUILE_ATTR }).addTo(carte);
      LRef.current = L as unknown as typeof import("leaflet");
      carteRef.current = carte;
      setPret(true);
    });

    return () => {
      if (carteRef.current) {
        carteRef.current.remove();
        carteRef.current = null;
      }
    };
  }, []);

  // Bascule fond de carte OSM ↔ Satellite
  useEffect(() => {
    const L = LRef.current;
    const carte = carteRef.current;
    if (!L || !carte || !pret) return;
    if (tileLayerRef.current) (tileLayerRef.current as LeafletTile).remove();
    if (satellite) {
      tileLayerRef.current = L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        { attribution: "Tiles &copy; Esri", maxZoom: 19 },
      ).addTo(carte);
    } else {
      tileLayerRef.current = L.tileLayer(TUILE_URL, { attribution: TUILE_ATTR, maxZoom: 19 }).addTo(carte);
    }
  }, [satellite, pret]);

  // Mise à jour des markers quand les incidents changent
  useEffect(() => {
    if (!pret || !carteRef.current) return;

    import("leaflet").then((L) => {
      const carte = carteRef.current;
      if (!carte) return;

      // Supprime les markers existants (CircleMarker uniquement)
      carte.eachLayer((layer) => {
        if (layer instanceof L.CircleMarker) {
          carte.removeLayer(layer);
        }
      });

      const maintenant = Date.now();

      incidents.forEach((inc) => {
        if (inc.lat == null || inc.lon == null) return;

        const ageMs = maintenant - new Date(inc.horodatage_publication).getTime();
        const actif = ageMs < 30 * 24 * 3600 * 1000;
        const couleur = couleurSeverite(inc.severite);
        const opacite = actif ? 1 : 0.35;

        // Heure relative lisible
        const ageH = Math.floor(ageMs / 3600000);
        const ageMin = Math.floor((ageMs % 3600000) / 60000);
        const ageLibelle =
          ageH > 0
            ? `il y a ${ageH}h${ageMin > 0 ? ageMin + "min" : ""}`
            : `il y a ${ageMin}min`;

        const marker = L.circleMarker([inc.lat, inc.lon], {
          radius: 10,
          color: couleur,
          fillColor: couleur,
          fillOpacity: opacite,
          opacity: opacite,
          weight: 2,
        });

        const typeLibelle: Record<string, string> = {
          accident: t("incidents.typeAccident"),
          embouteillage: t("incidents.typeEmbouteillage"),
          route_barree: t("incidents.typeRouteBarree"),
          travaux: t("incidents.typeTravaux"),
          autre: t("incidents.typeAutre"),
        };

        const badgeActif = actif
          ? `<span style="background:#dc2626;color:#fff;padding:1px 6px;border-radius:4px;font-size:11px;margin-left:6px;">ACTIF</span>`
          : "";

        marker.bindPopup(
          `<div style="max-width:240px;font-family:sans-serif;">
            <strong style="font-size:13px;">${inc.titre}${badgeActif}</strong><br/>
            <span style="color:#6b7280;font-size:12px;">${typeLibelle[inc.type_incident ?? ""] ?? inc.type_incident ?? ""}</span><br/>
            <span style="font-size:12px;color:#374151;">${inc.resume?.slice(0, 150) ?? ""}${(inc.resume?.length ?? 0) > 150 ? "…" : ""}</span><br/>
            <hr style="margin:4px 0;border:none;border-top:1px solid #e5e7eb;"/>
            <span style="font-size:11px;color:#9ca3af;">${inc.source_nom} · ${ageLibelle}</span>
            ${inc.troncon_id ? `<br/><span style="font-size:11px;color:#1d4ed8;">Tronçon #${inc.troncon_id}</span>` : ""}
          </div>`
        );

        marker.addTo(carte!);
      });
    });
  }, [pret, incidents, t]);

  return (
    <div
      className="relative overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700"
      style={{ height: "380px", width: "100%" }}
    >
      <div ref={conteneurRef} className="absolute inset-0" />
      <button
        onClick={() => setSatellite((v) => !v)}
        title={satellite ? "Vue OSM" : "Vue satellite"}
        className="absolute bottom-6 left-2 z-[1050] flex items-center gap-1 rounded bg-white/95
                   px-2 py-1 text-xs font-semibold shadow border border-gray-200
                   hover:bg-blue-50 dark:bg-gray-800/95 dark:border-gray-600 dark:text-gray-100"
      >
        {satellite ? "🗺 OSM" : "🛰 Satellite"}
      </button>
    </div>
  );
}

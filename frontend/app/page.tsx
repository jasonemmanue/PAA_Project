"use client";

/**
 * Page d'accueil = vue Carte. Toute la logique est encapsulée dans le
 * composant `PageCarte` (Leaflet + WebSocket + heatmap + panneau liste).
 */

import { PageCarte } from "@/components/carte/PageCarte";

export default function PageAccueil() {
  return <PageCarte />;
}

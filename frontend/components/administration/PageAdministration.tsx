"use client";

/**
 * Page Administration (P6.4) — orchestrateur 2 onglets.
 *
 * Récupère la liste des tronçons existants (filtre actifs+inactifs pour
 * pouvoir distinguer dans la table), puis affiche l'onglet sélectionné.
 */

import { useCallback, useEffect, useState } from "react";

import { OngletAxes } from "@/components/administration/OngletAxes";
import { OngletSousTroncons } from "@/components/administration/OngletSousTroncons";
import { PageHeader } from "@/components/ui/PageHeader";
import { api } from "@/lib/api";
import type { TronconAdmin } from "@/lib/types";

type Onglet = "axes" | "sous_troncons";

export function PageAdministration() {
  const [onglet, setOnglet] = useState<Onglet>("axes");
  const [troncons, setTroncons] = useState<TronconAdmin[]>([]);
  const [chargement, setChargement] = useState(true);

  const charger = useCallback(async () => {
    setChargement(true);
    try {
      // L'endpoint /troncons renvoie un objet { troncons: [...] } enrichi
      // par construire_etat_carte() : coords sous `geometrie.*`, `actif`
      // implicite (le backend filtre déjà actif=true par défaut),
      // `couleur` exposée sous `couleur_base`. On normalise ici pour que
      // l'admin ait le shape `TronconAdmin` même si l'API change un jour.
      const data = await api.troncons();
      type TronconBrut = {
        id: number; nom: string;
        lat_origine?: number | null; lon_origine?: number | null;
        lat_destination?: number | null; lon_destination?: number | null;
        geometrie?: {
          lat_origine: number | null; lon_origine: number | null;
          lat_destination: number | null; lon_destination: number | null;
        };
        polyline: string | null;
        distance_m: number; vitesse_ref_kmh: number;
        couleur?: string; couleur_base?: string;
        actif?: boolean;
      };
      const brut = (Array.isArray(data) ? data : []) as TronconBrut[];
      setTroncons(
        brut.map((t) => ({
          id: t.id,
          nom: t.nom,
          // Coords : top-level OU sous `geometrie.*` (payload /carte/etat)
          lat_origine: t.lat_origine ?? t.geometrie?.lat_origine ?? null,
          lon_origine: t.lon_origine ?? t.geometrie?.lon_origine ?? null,
          lat_destination:
            t.lat_destination ?? t.geometrie?.lat_destination ?? null,
          lon_destination:
            t.lon_destination ?? t.geometrie?.lon_destination ?? null,
          polyline: t.polyline,
          distance_m: t.distance_m,
          distance_km: Math.round((t.distance_m / 1000) * 100) / 100,
          vitesse_ref_kmh: t.vitesse_ref_kmh,
          couleur: t.couleur ?? t.couleur_base ?? "#3498DB",
          // L'endpoint ne renvoie que les actifs par défaut → si le champ
          // est absent, on considère le tronçon actif.
          actif: t.actif ?? true,
        })),
      );
    } finally {
      setChargement(false);
    }
  }, []);

  useEffect(() => {
    void charger();
  }, [charger]);

  return (
    <div className="flex flex-col gap-fluid-4">
      <PageHeader
        titre="Administration — axes & tronçons"
        sousTitre="Ajoutez de nouveaux axes ou subdivisez-les en tronçons codifiés (T1A, T1B…) selon la convention DEESP. Suppression toujours logique : l'historique est préservé."
      />

      {/* Onglets */}
      <div className="inline-flex flex-wrap gap-1 rounded-md border app-border p-1 app-surface self-start">
        <button
          type="button"
          onClick={() => setOnglet("axes")}
          aria-pressed={onglet === "axes"}
          className={
            "px-4 py-2 text-fluid-sm font-medium rounded transition-colors " +
            (onglet === "axes"
              ? "bg-paa-navy-700 text-white"
              : "text-paa-navy-700 hover:bg-paa-blue-50 dark:text-paa-blue-100 dark:hover:bg-paa-navy-700")
          }
        >
          🛣 Axes principaux
        </button>
        <button
          type="button"
          onClick={() => setOnglet("sous_troncons")}
          aria-pressed={onglet === "sous_troncons"}
          className={
            "px-4 py-2 text-fluid-sm font-medium rounded transition-colors " +
            (onglet === "sous_troncons"
              ? "bg-paa-navy-700 text-white"
              : "text-paa-navy-700 hover:bg-paa-blue-50 dark:text-paa-blue-100 dark:hover:bg-paa-navy-700")
          }
        >
          🔬 Tronçons codifiés (T1A…)
        </button>
      </div>

      {chargement && (
        <p className="text-fluid-xs app-text-muted">Chargement des tronçons…</p>
      )}

      {!chargement && onglet === "axes" && (
        <OngletAxes troncons={troncons} onChange={charger} />
      )}
      {!chargement && onglet === "sous_troncons" && (
        <OngletSousTroncons troncons={troncons} onChange={charger} />
      )}
    </div>
  );
}

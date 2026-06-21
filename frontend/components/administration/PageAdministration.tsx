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
      // L'endpoint /troncons renvoie un objet { troncons: [...] } enrichi —
      // on prend directement le tableau pour l'admin.
      const data = await api.troncons();
      setTroncons(
        (Array.isArray(data) ? data : []).map((t) => ({
          id: t.id,
          nom: t.nom,
          lat_origine: t.lat_origine,
          lon_origine: t.lon_origine,
          lat_destination: t.lat_destination,
          lon_destination: t.lon_destination,
          polyline: t.polyline,
          distance_m: t.distance_m,
          distance_km: Math.round((t.distance_m / 1000) * 100) / 100,
          vitesse_ref_kmh: t.vitesse_ref_kmh,
          couleur: t.couleur,
          actif: t.actif,
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
        titre="Administration — tronçons & sous-tronçons"
        sousTitre="Ajoutez de nouveaux axes ou subdivisez-les en sous-tronçons codifiés (T1A, T1B…) selon la convention DEESP. Suppression toujours logique : l'historique est préservé."
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
          🔬 Sous-tronçons codifiés (T1A…)
        </button>
      </div>

      {chargement && (
        <p className="text-fluid-xs app-text-muted">Chargement des tronçons…</p>
      )}

      {!chargement && onglet === "axes" && (
        <OngletAxes troncons={troncons} onChange={charger} />
      )}
      {!chargement && onglet === "sous_troncons" && (
        <OngletSousTroncons troncons={troncons} />
      )}
    </div>
  );
}

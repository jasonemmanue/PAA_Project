"use client";

/**
 * Page Rapport — reproduit fidèlement les 17 tableaux et 12 graphiques du
 * rapport officiel DEESP/DEEF (cf. CLAUDE.md § 4.5).
 *
 * Structure :
 *   1. Sélecteur de campagne (AAAA-MM)
 *   2. Tableau 1 — Temps théoriques 50 km/h
 *   3. Tableaux 3-7 — Temps minimal par axe × type-jour
 *   4. Graphiques 1, 3, 5 + 2, 4, 6 — BarChart min observé par jour
 *   5. Tableaux 8-11 — Temps moyen
 *   6. Tableaux 12-15 — Temps maximal
 *   7. Graphiques 7, 9, 11 + 8, 10, 12 — BarChart max observé
 *   8. Tableau 16 — Zones congestionnées (règles DEESP)
 *   9. Tableau 17 — Synthèse comparative
 */

import { useCallback, useEffect, useState } from "react";

import { PageHeader } from "@/components/ui/PageHeader";
import { TableauTempsTheoriques } from "@/components/rapport/TableauTempsTheoriques";
import { TableauTempsTraversee } from "@/components/rapport/TableauTempsTraversee";
import { TableauZonesCongestionnees } from "@/components/rapport/TableauZonesCongestionnees";
import { GraphiquesParAxe } from "@/components/rapport/GraphiquesParAxe";
import { api } from "@/lib/api";
import type {
  RapportTempsTheoriques,
  RapportTempsTraversee,
  RapportZonesCongestionnees,
  Troncon,
} from "@/lib/types";

function defautCampagne(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function PageRapport() {
  const [campagne, setCampagne] = useState<string>(defautCampagne());
  const [theoriques, setTheoriques] = useState<RapportTempsTheoriques | null>(null);
  const [traversee, setTraversee] = useState<RapportTempsTraversee | null>(null);
  const [zones, setZones] = useState<RapportZonesCongestionnees | null>(null);
  const [troncons, setTroncons] = useState<Troncon[]>([]);
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState<string | null>(null);

  const recharger = useCallback(async () => {
    setChargement(true);
    setErreur(null);
    try {
      const [t, tt, ttv, zc] = await Promise.all([
        api.troncons(),
        api.rapportTempsTheoriques(),
        api.rapportTempsTraversee(campagne),
        api.rapportZonesCongestionnees(campagne),
      ]);
      setTroncons(Array.isArray(t) ? t : []);
      setTheoriques(tt);
      setTraversee(ttv);
      setZones(zc);
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setChargement(false);
    }
  }, [campagne]);

  useEffect(() => {
    recharger();
  }, [recharger]);

  return (
    <div className="flex flex-col gap-fluid-4">
      <PageHeader
        titre="Rapport DEESP — Évaluation du temps de traversée"
        sousTitre="Reproduit la structure officielle du rapport DEESP/DEEF (17 tableaux, 12 graphiques)"
      />

      {/* Sélecteur de campagne */}
      <div className="paa-card flex flex-wrap items-end gap-4 p-fluid-4">
        <label className="flex flex-col gap-1">
          <span className="text-fluid-xs font-medium app-text-muted">
            Campagne (AAAA-MM)
          </span>
          <input
            type="month"
            value={campagne}
            onChange={(e) => setCampagne(e.target.value)}
            className="rounded-md border app-border app-surface px-3 py-2 text-fluid-sm
                       text-paa-navy-900 focus:outline-none focus:ring-2 focus:ring-paa-blue-400
                       dark:text-paa-blue-100 min-h-[40px]"
          />
        </label>
        <div className="text-fluid-xs app-text-muted">
          La campagne couvre du 1er au dernier jour du mois sélectionné. <br />
          Méthodologie : 1 mesure/heure × 12 heures × 6 tronçons × ~30 jours.
        </div>
      </div>

      {erreur && (
        <div className="rounded-md bg-statut-congestionne/10 border border-statut-congestionne/40 px-3 py-2 text-fluid-sm text-statut-congestionne">
          Erreur : {erreur}
        </div>
      )}

      {/* Tableau 1 */}
      <TableauTempsTheoriques rapport={theoriques} />

      {/* Tableaux 3-7 / 8-11 / 12-15 + récap 17 */}
      <TableauTempsTraversee
        rapport={traversee}
        agregat="min"
        titre="Tableaux 3-7 — Temps MINIMAL observé"
        description="Pour chaque tronçon, en minutes, par type de jour (ouvrable / week-end)."
      />
      <TableauTempsTraversee
        rapport={traversee}
        agregat="moyen"
        titre="Tableaux 8-11 — Temps MOYEN observé"
        description="Moyenne des moyennes journalières — méthode DEESP."
      />
      <TableauTempsTraversee
        rapport={traversee}
        agregat="max"
        titre="Tableaux 12-15 — Temps MAXIMAL observé"
        description="Pour chaque tronçon, en minutes, par type de jour."
      />

      {/* Graphiques 1-12 */}
      <GraphiquesParAxe
        troncons={troncons}
        campagne={campagne}
        agregat="min"
        titre="Graphiques 1-6 — Temps MIN observé par jour (BarChart)"
      />
      <GraphiquesParAxe
        troncons={troncons}
        campagne={campagne}
        agregat="max"
        titre="Graphiques 7-12 — Temps MAX observé par jour (BarChart)"
      />

      {/* Tableau 16 */}
      <TableauZonesCongestionnees rapport={zones} />

      {chargement && (
        <p className="text-fluid-xs app-text-muted">Chargement…</p>
      )}
    </div>
  );
}

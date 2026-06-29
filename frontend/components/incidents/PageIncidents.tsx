"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Incident, IncidentsPage, StatsIncidents, Troncon } from "@/lib/types";

import { FiltresIncidents, type FiltresEtat } from "./FiltresIncidents";
import { GestionSources } from "./GestionSources";
import { GestionTypes } from "./GestionTypes";
import { ListeIncidents } from "./ListeIncidents";

// Leaflet est client-only — chargement dynamique sans SSR
const CarteIncidents = dynamic(
  () => import("./CarteIncidents").then((m) => m.CarteIncidents),
  { ssr: false, loading: () => <div className="h-96 bg-gray-100 dark:bg-gray-800 rounded-lg animate-pulse" /> }
);

// Intervalle de polling en ms (5 min)
const POLLING_MS = 5 * 60 * 1000;

function filtrerParPeriode(incidents: Incident[], periode: FiltresEtat["periode"]): Incident[] {
  const maintenant = Date.now();
  const limites: Record<FiltresEtat["periode"], number> = {
    "aujourd'hui": new Date().setHours(0, 0, 0, 0),
    "24h": maintenant - 24 * 3600 * 1000,
    "7j":  maintenant - 7  * 24 * 3600 * 1000,
  };
  const limite = limites[periode];
  return incidents.filter(
    (i) => new Date(i.horodatage_publication).getTime() >= limite
  );
}

export function PageIncidents() {
  const { t } = useI18n();

  const [troncons, setTroncons]   = useState<Troncon[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [stats, setStats]         = useState<StatsIncidents | null>(null);
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur]         = useState<string | null>(null);

  const [filtres, setFiltres] = useState<FiltresEtat>({
    type: "",
    periode: "24h",
    troncon_id: null,
  });

  // -------------------------------------------------------------------------
  // Chargement initial + polling
  // -------------------------------------------------------------------------

  async function charger() {
    const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8081";
    console.group("[PageIncidents] charger()");
    console.log("API base URL :", base);
    try {
      console.log("→ GET /incidents?limit=200");
      const page = await api.getIncidents({ limit: 200 }).catch((e) => {
        console.error("❌ /incidents :", e?.statut, e?.message, e?.corps);
        throw e;
      });
      console.log("✓ /incidents →", page.total, "incident(s)");

      console.log("→ GET /incidents/stats");
      const statsData = await api.getStatsIncidents().catch((e) => {
        console.error("❌ /incidents/stats :", e?.statut, e?.message, e?.corps);
        throw e;
      });
      console.log("✓ /incidents/stats →", statsData);

      console.log("→ GET /troncons");
      const trs = await api.troncons().catch((e) => {
        console.error("❌ /troncons :", e?.statut, e?.message, e?.corps);
        throw e;
      });
      console.log("✓ /troncons →", trs.length, "tronçon(s)");

      setIncidents(page.items);
      setStats(statsData);
      setTroncons(trs);
      setErreur(null);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      console.error("❌ Erreur globale charger() :", e);
      setErreur(msg);
    } finally {
      setChargement(false);
      console.groupEnd();
    }
  }

  useEffect(() => {
    charger();
    const id = setInterval(charger, POLLING_MS);
    return () => clearInterval(id);
  }, []);

  // -------------------------------------------------------------------------
  // Filtrage côté client
  // -------------------------------------------------------------------------

  const incidentsFiltres = (() => {
    let liste = filtrerParPeriode(incidents, filtres.periode);
    if (filtres.type)        liste = liste.filter((i) => i.type_incident === filtres.type);
    if (filtres.troncon_id)  liste = liste.filter((i) => i.troncon_id === filtres.troncon_id);
    return liste;
  })();

  // Incidents actifs pour la carte (< 6 h, géolocalisés)
  const incidentsActifs = incidents.filter(
    (i) => i.actif && i.lat != null && i.lon != null
  );

  // Accidents groupés par mois (format "YYYY-MM")
  const accidentsParMois: { mois: string; nb: number }[] = (() => {
    const carte = new Map<string, number>();
    incidents
      .filter((i) => i.type_incident === "accident")
      .forEach((i) => {
        const d = new Date(i.horodatage_publication);
        const cle = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
        carte.set(cle, (carte.get(cle) ?? 0) + 1);
      });
    return Array.from(carte.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([mois, nb]) => ({ mois, nb }));
  })();

  // Tronçon le plus impacté
  const tronconImpacte = (() => {
    if (!stats || !troncons.length) return null;
    const comptes: Record<number, number> = {};
    incidents.forEach((i) => {
      if (i.troncon_id) comptes[i.troncon_id] = (comptes[i.troncon_id] ?? 0) + 1;
    });
    const maxId = Object.entries(comptes).sort(([, a], [, b]) => b - a)[0]?.[0];
    return maxId ? troncons.find((tr) => tr.id === Number(maxId))?.nom ?? null : null;
  })();

  // -------------------------------------------------------------------------
  // Rendu
  // -------------------------------------------------------------------------

  if (chargement) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="text-gray-500 animate-pulse">{t("common.loading")}</span>
      </div>
    );
  }

  if (erreur) {
    return (
      <div className="p-6 text-red-600 dark:text-red-400">
        {t("common.error")} : {erreur}
      </div>
    );
  }

  const nbActifs = stats?.nb_actifs ?? 0;
  const nbAujourdhui = incidentsFiltres.length;

  return (
    <div className="flex flex-col gap-fluid-4">
      {/* En-tête */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          {t("incidents.titre")}
          {nbActifs > 0 && (
            <span className="ml-3 inline-flex items-center px-2.5 py-0.5 rounded-full text-sm font-medium bg-red-500 text-white animate-pulse">
              {nbActifs}
            </span>
          )}
        </h1>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
          {t("incidents.subtitle")}
        </p>
      </div>

      {/* KPI compacts */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="paa-card p-4">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
            {t("incidents.nbActifs")}
          </p>
          <p className="text-3xl font-bold text-red-600 dark:text-red-400">{nbActifs}</p>
        </div>
        <div className="paa-card p-4">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
            {t("incidents.nbAujourdhui")}
          </p>
          <p className="text-3xl font-bold text-gray-900 dark:text-gray-100">{nbAujourdhui}</p>
        </div>
        <div className="paa-card p-4">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
            {t("incidents.tronconImpacte")}
          </p>
          <p className="text-base font-semibold text-gray-900 dark:text-gray-100 truncate">
            {tronconImpacte ?? "—"}
          </p>
        </div>
      </div>

      {/* Carte des incidents actifs */}
      <div className="paa-card p-4">
        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
          {t("incidents.carteTitle")}
        </h2>
        <CarteIncidents incidents={incidentsActifs} />
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-2">
          {incidentsActifs.length === 0
            ? t("incidents.aucunIncidentCarte")
            : `${incidentsActifs.length} incident(s) géolocalisé(s) affiché(s)`}
        </p>
      </div>

      {/* Filtres */}
      <div className="paa-card p-4">
        <FiltresIncidents
          filtres={filtres}
          onChange={setFiltres}
          troncons={troncons}
          apiBaseUrl={process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8081"}
        />
      </div>

      {/* Gestion des sources et des types — visible en mode écriture uniquement */}
      <GestionSources />
      <GestionTypes />

      {/* Accidents par mois */}
      {accidentsParMois.length > 0 && (
        <div className="paa-card p-4">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
            Accidents par mois
          </h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={accidentsParMois} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.08)" />
              <XAxis dataKey="mois" tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
              <Tooltip
                formatter={(v: number) => [`${v} accident(s)`, "Accidents"]}
                labelFormatter={(l) => `Mois : ${l}`}
              />
              <Bar dataKey="nb" name="Accidents" radius={[3, 3, 0, 0]}>
                {accidentsParMois.map((_entry, i) => (
                  <Cell key={i} fill="#dc2626" />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Liste chronologique */}
      <div className="paa-card p-4">
        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
          {incidentsFiltres.length} {t("incidents.incidentsRecenses")}
        </h2>
        <ListeIncidents incidents={incidentsFiltres} />
      </div>
    </div>
  );
}

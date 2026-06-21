"use client";

/**
 * Onglet "Heure optimale" de la page Prédiction (P6.3).
 *
 * Workflow utilisateur :
 *   1. Saisir un point de départ (nom de lieu ou "lat,lon")
 *   2. Choisir une date
 *   3. Bouton "Calculer" → POST /heure-optimale
 *   4. Affichage :
 *      - Encadré recommandation textuelle
 *      - 2 KPI : créneau optimal vs créneau pire
 *      - BarChart Recharts : 24 créneaux toutes les 30 min, axe Y = total mn
 *      - Détails approche libre (méthode utilisée : OSRM ou Haversine)
 */

import { useState } from "react";
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

import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { HeureOptimaleResponse } from "@/lib/types";

const COULEUR_OPTIMAL = "#2ECC71";
const COULEUR_PIRE = "#E74C3C";
const COULEUR_NORMAL = "#3498DB";

function defautDate(): string {
  return new Date().toISOString().slice(0, 10);
}

export function OngletHeureOptimale() {
  const [depart, setDepart] = useState<string>("");
  const [dateCible, setDateCible] = useState<string>(defautDate());
  const [resultat, setResultat] = useState<HeureOptimaleResponse | null>(null);
  const [chargement, setChargement] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const lancer = async () => {
    if (!depart.trim()) {
      setErreur("Indiquez un point de départ (nom de lieu ou coordonnées lat,lon)");
      return;
    }
    setChargement(true);
    setErreur(null);
    try {
      const r = await api.heureOptimale(depart, dateCible);
      setResultat(r);
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setChargement(false);
    }
  };

  return (
    <div className="flex flex-col gap-fluid-4">
      {/* Formulaire */}
      <Card
        titre="Quand partir vers le port ?"
        description="Indiquez votre point de départ et la date du trajet. Nous calculons la meilleure heure pour minimiser le temps total (approche libre + traversée portuaire)."
      >
        <div className="grid gap-3 md:grid-cols-[2fr_1fr_auto] md:items-end">
          <label className="flex flex-col gap-1 text-fluid-sm font-medium">
            Point de départ
            <input
              type="text"
              value={depart}
              onChange={(e) => setDepart(e.target.value)}
              placeholder="ex. Plateau Abidjan • ou 5.328,-4.028"
              className="rounded-md border app-border app-surface px-3 py-2 text-fluid-base
                         focus:outline-none focus:ring-2 focus:ring-paa-blue-400 min-h-[42px]"
            />
          </label>

          <label className="flex flex-col gap-1 text-fluid-sm font-medium">
            Date
            <input
              type="date"
              value={dateCible}
              onChange={(e) => setDateCible(e.target.value)}
              className="rounded-md border app-border app-surface px-3 py-2 text-fluid-base
                         focus:outline-none focus:ring-2 focus:ring-paa-blue-400 min-h-[42px]"
            />
          </label>

          <button
            type="button"
            onClick={lancer}
            disabled={chargement || !depart.trim()}
            className="btn-primary disabled:opacity-50 min-h-[42px]"
          >
            {chargement ? "Calcul…" : "Calculer la meilleure heure"}
          </button>
        </div>
      </Card>

      {erreur && (
        <div className="rounded-md bg-statut-congestionne/10 border border-statut-congestionne/40 px-3 py-2 text-fluid-sm text-statut-congestionne">
          {erreur}
        </div>
      )}

      {resultat && (
        <>
          {/* Recommandation textuelle */}
          <Card titre="Notre recommandation">
            <p className="text-fluid-base text-paa-navy-900 dark:text-paa-blue-100 leading-relaxed">
              {resultat.recommandation}
            </p>
            <p className="mt-3 text-fluid-xs app-text-muted">
              📍 Départ géocodé : <em>{resultat.depart.adresse}</em>
              <br />
              🛣 Tronçon d'arrivée :{" "}
              <strong>{resultat.troncon_utilise.nom}</strong>
              <br />
              ⏱ Approche libre estimée :{" "}
              <strong>{resultat.approche_libre_mn} min</strong> (
              {resultat.methode_approche === "osrm"
                ? "via OSRM, suit le réseau routier"
                : "repli Haversine ÷ 30 km/h, OSRM indisponible"}
              )
              <br />
              📅 Type de jour : <strong>{resultat.type_jour === "jour_ouvrable" ? "jour ouvrable" : "week-end"}</strong>
            </p>
          </Card>

          {/* 2 KPI cards */}
          <div className="grid gap-fluid-4 md:grid-cols-2">
            <KpiCreneau
              label="🏆 Meilleur créneau"
              creneau={resultat.creneau_optimal.depart}
              totalMn={resultat.creneau_optimal.total_mn}
              couleur={COULEUR_OPTIMAL}
              soustitre={`Gain de ${resultat.creneau_optimal.gain_vs_pire_mn} min vs le pire`}
            />
            <KpiCreneau
              label="⚠️ Créneau à éviter"
              creneau={resultat.creneau_pire.depart}
              totalMn={resultat.creneau_pire.total_mn}
              couleur={COULEUR_PIRE}
              soustitre={`+${resultat.creneau_optimal.gain_vs_pire_mn} min vs l'optimal`}
            />
          </div>

          {/* BarChart 24 créneaux */}
          <Card
            titre="Temps total par créneau de départ"
            description="Axe Y en minutes — 1 barre = 1 créneau toutes les 30 min."
          >
            <div className="h-72 w-full sm:h-80">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={resultat.creneaux} margin={{ top: 10, right: 5, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis
                    dataKey="depart"
                    tick={{ fontSize: 10 }}
                    interval={1}
                  />
                  <YAxis tick={{ fontSize: 10 }} unit=" mn" />
                  <Tooltip
                    formatter={(v: unknown, name: string) => {
                      if (name === "total_mn") return [`${v} min`, "Temps total"];
                      return [v as string, name];
                    }}
                    labelFormatter={(label) => `Départ ${label}`}
                  />
                  <Bar dataKey="total_mn" fill={COULEUR_NORMAL}>
                    {resultat.creneaux.map((c, idx) => {
                      const couleur =
                        c.depart === resultat.creneau_optimal.depart
                          ? COULEUR_OPTIMAL
                          : c.depart === resultat.creneau_pire.depart
                            ? COULEUR_PIRE
                            : COULEUR_NORMAL;
                      return <Cell key={idx} fill={couleur} />;
                    })}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-2 flex flex-wrap gap-3 text-fluid-xs app-text-muted">
              <LegendeItem couleur={COULEUR_OPTIMAL} label="Optimal" />
              <LegendeItem couleur={COULEUR_PIRE} label="À éviter" />
              <LegendeItem couleur={COULEUR_NORMAL} label="Standard" />
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

function KpiCreneau({
  label,
  creneau,
  totalMn,
  couleur,
  soustitre,
}: {
  label: string;
  creneau: string;
  totalMn: number;
  couleur: string;
  soustitre: string;
}) {
  return (
    <div
      className="paa-card p-fluid-4"
      style={{ borderLeft: `4px solid ${couleur}` }}
    >
      <div className="text-fluid-xs font-medium app-text-muted">{label}</div>
      <div className="mt-1 text-fluid-3xl font-bold" style={{ color: couleur }}>
        {creneau}
      </div>
      <div className="mt-1 text-fluid-base font-semibold text-paa-navy-900 dark:text-paa-blue-100">
        Total {totalMn} min
      </div>
      <div className="mt-1 text-fluid-xs app-text-muted">{soustitre}</div>
    </div>
  );
}

function LegendeItem({ couleur, label }: { couleur: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span
        className="inline-block h-3 w-3 rounded-sm"
        style={{ backgroundColor: couleur }}
      />
      {label}
    </span>
  );
}

"use client";

/**
 * Page Temps de traversée par période.
 *
 * Affiche 3 blocs empilés de haut en bas :
 *   1. Temps actuel   — estimation cascade Google → profils → 50 km/h
 *                       (précision améliorée par les relevés GPX terrain — page Fiabilité)
 *   2. Ce mois        — stats Google réelles depuis le 1er du mois
 *   3. Cette semaine  — stats Google réelles depuis le lundi en cours
 *
 * Aucun sélecteur de date ou d'heure — tout est automatique.
 */

import { useEffect, useState } from "react";

import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { api } from "@/lib/api";
import type { ResumePrediction, SourcePrediction, StatsPeriode, Troncon } from "@/lib/types";

const COULEUR_SOURCE: Record<SourcePrediction, string> = {
  google_routes: "#2ECC71",
  mesures_jour_type_7j: "#3498DB",
  vitesse_ref_50kmh: "#95A5A6",
};

const LIBELLE_SOURCE: Record<SourcePrediction, string> = {
  google_routes: "Mesure Google temps réel",
  mesures_jour_type_7j: "Mesures récentes même type de jour (7 j, calibré GPX)",
  vitesse_ref_50kmh: "Référence 50 km/h",
};

function formaterDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  const mois = ["", "jan.", "fév.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
  return `${Number(d)} ${mois[Number(m)]} ${y}`;
}

export function PagePrediction() {
  const [troncons, setTroncons] = useState<Troncon[]>([]);
  const [tronconId, setTronconId] = useState<number | null>(null);
  const [resume, setResume] = useState<ResumePrediction | null>(null);
  const [chargement, setChargement] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    let annule = false;
    api.troncons().then((liste) => {
      if (annule) return;
      const tr = Array.isArray(liste) ? liste : [];
      setTroncons(tr);
      setTronconId(tr[0]?.id ?? null);
    }).catch((e) => !annule && setErreur(e instanceof Error ? e.message : String(e)));
    return () => { annule = true; };
  }, []);

  useEffect(() => {
    if (tronconId === null) return;
    let annule = false;
    setChargement(true);
    setErreur(null);
    api.resumePrediction(tronconId)
      .then((r) => { if (!annule) setResume(r); })
      .catch((e) => { if (!annule) setErreur(e instanceof Error ? e.message : String(e)); })
      .finally(() => { if (!annule) setChargement(false); });
    return () => { annule = true; };
  }, [tronconId]);

  return (
    <div className="flex flex-col gap-fluid-4">
      <PageHeader
        titre="Temps de traversée par période"
        sousTitre="Temps min / moyen / max observés — période courante, ce mois et cette semaine. L'estimation courante est calibrée par les relevés GPX terrain (page Fiabilité)."
      />

      {/* Sélecteur tronçon */}
      <Card>
        <label className="flex flex-col gap-1 text-fluid-sm font-medium max-w-md">
          Tronçon
          <select
            value={tronconId ?? ""}
            onChange={(e) => setTronconId(Number(e.target.value))}
            className="rounded-md border app-border app-surface px-3 py-2 text-fluid-base
                       focus:outline-none focus:ring-2 focus:ring-paa-blue-400 min-h-[42px]"
          >
            {troncons.map((tr) => (
              <option key={tr.id} value={tr.id}>{tr.nom}</option>
            ))}
          </select>
        </label>
      </Card>

      {erreur && (
        <div className="rounded-md bg-statut-congestionne/10 border border-statut-congestionne/40 px-3 py-2 text-fluid-sm text-statut-congestionne">
          Erreur : {erreur}
        </div>
      )}

      {chargement && (
        <div className="text-fluid-sm app-text-muted animate-pulse">Chargement…</div>
      )}

      {resume && !chargement && (
        <>
          {/* ─── 1. TEMPS ACTUEL ─────────────────────────────────────────── */}
          <section>
            <h2 className="text-fluid-lg font-semibold text-paa-navy-700 dark:text-paa-blue-100 mb-2">
              🕐 Temps actuel
            </h2>
            <div className="flex flex-wrap gap-2 mb-3">
              <BadgeSource source={resume.courante.source} />
              <BadgeTypeJour type={resume.courante.type_jour} />
              <BadgeConfiance valeur={resume.courante.confiance} />
            </div>
            <div className="grid gap-fluid-4 md:grid-cols-3">
              <KpiMn label="Temps minimum" mn={resume.courante.prediction.min_mn} couleur="#2ECC71" />
              <KpiMn label="Temps moyen" mn={resume.courante.prediction.moyen_mn} couleur="#3498DB" dominante />
              <KpiMn label="Temps maximum" mn={resume.courante.prediction.max_mn} couleur="#E74C3C" />
            </div>
          </section>

          {/* ─── 2. CE MOIS ──────────────────────────────────────────────── */}
          <section>
            <h2 className="text-fluid-lg font-semibold text-paa-navy-700 dark:text-paa-blue-100 mb-1">
              📆 Ce mois
            </h2>
            <p className="text-fluid-xs app-text-muted mb-3">
              {formaterDate(resume.mois.debut)} → {formaterDate(resume.mois.fin)}
              {" — "}{resume.mois.nb_mesures_total} mesure{resume.mois.nb_mesures_total !== 1 ? "s" : ""} Google
            </p>
            <div className="grid gap-fluid-4 md:grid-cols-2">
              <BlocTypeJour titre="Jours ouvrables (lun–ven)" stats={resume.mois.jours_ouvrables} />
              <BlocTypeJour titre="Week-ends (sam–dim)" stats={resume.mois.week_ends} />
            </div>
          </section>

          {/* ─── 3. CETTE SEMAINE ────────────────────────────────────────── */}
          <section>
            <h2 className="text-fluid-lg font-semibold text-paa-navy-700 dark:text-paa-blue-100 mb-1">
              📅 Cette semaine
            </h2>
            <p className="text-fluid-xs app-text-muted mb-3">
              {formaterDate(resume.semaine.debut)} → {formaterDate(resume.semaine.fin)}
              {" — "}{resume.semaine.nb_mesures_total} mesure{resume.semaine.nb_mesures_total !== 1 ? "s" : ""} Google
            </p>
            <div className="grid gap-fluid-4 md:grid-cols-2">
              <BlocTypeJour titre="Jours ouvrables (lun–ven)" stats={resume.semaine.jours_ouvrables} />
              <BlocTypeJour titre="Week-ends (sam–dim)" stats={resume.semaine.week_ends} />
            </div>
          </section>

        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sous-composants
// ---------------------------------------------------------------------------

function KpiMn({
  label,
  mn,
  couleur,
  dominante = false,
}: {
  label: string;
  mn: number | null;
  couleur: string;
  dominante?: boolean;
}) {
  return (
    <div
      className="paa-card p-fluid-4"
      style={dominante ? { borderLeft: `4px solid ${couleur}` } : undefined}
    >
      <div className="text-fluid-xs font-medium app-text-muted">{label}</div>
      <div className="mt-1 text-fluid-3xl font-bold" style={{ color: couleur }}>
        {mn === null ? "—" : `${mn} min`}
      </div>
    </div>
  );
}

function BlocTypeJour({ titre, stats }: { titre: string; stats: StatsPeriode | null }) {
  return (
    <div className="paa-card p-fluid-4">
      <div className="text-fluid-sm font-semibold text-paa-navy-700 dark:text-paa-blue-100 mb-3">
        {titre}
      </div>
      {stats === null ? (
        <p className="text-fluid-xs app-text-muted italic">Aucune mesure sur cette période.</p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div>
              <div className="text-fluid-xs app-text-muted">Min</div>
              <div className="text-fluid-xl font-bold text-statut-fluide">{stats.min_mn} min</div>
            </div>
            <div>
              <div className="text-fluid-xs app-text-muted">Moyen</div>
              <div className="text-fluid-xl font-bold text-paa-blue-500">{stats.moyen_mn} min</div>
            </div>
            <div>
              <div className="text-fluid-xs app-text-muted">Max</div>
              <div className="text-fluid-xl font-bold text-statut-congestionne">{stats.max_mn} min</div>
            </div>
          </div>
          <div className="mt-3 text-fluid-xs app-text-muted text-right">
            {stats.nb_mesures} mesure{stats.nb_mesures !== 1 ? "s" : ""}
          </div>
        </>
      )}
    </div>
  );
}

function BadgeSource({ source }: { source: SourcePrediction }) {
  const c = COULEUR_SOURCE[source];
  return (
    <span
      className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-fluid-xs font-medium"
      style={{ backgroundColor: `${c}22`, color: c, border: `1px solid ${c}` }}
    >
      <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: c }} />
      {LIBELLE_SOURCE[source]}
    </span>
  );
}

function BadgeTypeJour({ type }: { type: "jour_ouvrable" | "week_end" }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-paa-blue-100 px-3 py-1 text-fluid-xs font-medium text-paa-navy-700 dark:bg-paa-navy-700 dark:text-paa-blue-100">
      📅 {type === "jour_ouvrable" ? "Jour ouvrable" : "Week-end"}
    </span>
  );
}

function BadgeConfiance({ valeur }: { valeur: number }) {
  const pct = Math.round(valeur * 100);
  const c = valeur >= 0.7 ? "#2ECC71" : valeur >= 0.4 ? "#F39C12" : "#95A5A6";
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-3 py-1 text-fluid-xs font-medium"
      style={{ backgroundColor: `${c}22`, color: c, border: `1px solid ${c}` }}
    >
      Fiabilité {pct}%
    </span>
  );
}

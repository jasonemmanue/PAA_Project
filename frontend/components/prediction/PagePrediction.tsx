"use client";

/**
 * Page Temps de traversée par période.
 *
 * Source primaire : segments GPX terrain (mesures physiques réelles).
 * Source secondaire : estimation Google Routes (temps réel).
 *
 * Blocs :
 *   1. Terrain GPX — min/moyen/max de TOUTES les sessions importées
 *   2. Terrain GPX — cette semaine  (sessions de la semaine en cours)
 *   3. Terrain GPX — ce mois        (sessions du mois en cours)
 *   4. Google temps réel            (indicateur secondaire)
 */

import { useEffect, useState } from "react";

import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { api } from "@/lib/api";
import type {
  EstimationSession,
  ResumePrediction,
  ResumeSegments,
  SourcePrediction,
  Troncon,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// Helpers date
// ---------------------------------------------------------------------------

function lundiSemaine(): string {
  const d = new Date();
  const jour = d.getDay(); // 0=dim, 1=lun…
  const diff = (jour === 0 ? -6 : 1 - jour);
  d.setDate(d.getDate() + diff);
  return d.toISOString().slice(0, 10);
}

function premierDuMois(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

function formaterMn(s: number): string {
  const mn = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return `${mn}:${String(sec).padStart(2, "0")} min`;
}

function formaterDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  const mois = ["", "jan.", "fév.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
  return `${Number(d)} ${mois[Number(m)]} ${y}`;
}

// Filtre les sessions GPX selon une date minimale (YYYY-MM-DD)
function filtrerSessions(
  sessions: EstimationSession[],
  dateMin: string,
): EstimationSession[] {
  return sessions.filter((s) => s.date_session >= dateMin);
}

// Calcule min/moyen/max en secondes depuis une liste de sessions
function statsFromSessions(sessions: EstimationSession[]): { min: number; moyen: number; max: number } | null {
  const durees = sessions.map((s) => s.duree_totale_s);
  if (durees.length === 0) return null;
  return {
    min: Math.min(...durees),
    moyen: Math.round(durees.reduce((a, b) => a + b, 0) / durees.length),
    max: Math.max(...durees),
  };
}

const COULEUR_SOURCE: Record<SourcePrediction, string> = {
  google_routes: "#2ECC71",
  mesures_jour_type_7j: "#3498DB",
  vitesse_ref_50kmh: "#95A5A6",
};

const LIBELLE_SOURCE: Record<SourcePrediction, string> = {
  google_routes: "Mesure Google temps réel",
  mesures_jour_type_7j: "Mesures récentes même type de jour (7 j)",
  vitesse_ref_50kmh: "Référence 50 km/h",
};

// ---------------------------------------------------------------------------
// Composant principal
// ---------------------------------------------------------------------------

export function PagePrediction() {
  const [troncons, setTroncons] = useState<Troncon[]>([]);
  const [tronconId, setTronconId] = useState<number | null>(null);
  const [resume, setResume] = useState<ResumePrediction | null>(null);
  const [segments, setSegments] = useState<ResumeSegments | null>(null);
  const [chargement, setChargement] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    let annule = false;
    api.troncons().then((liste) => {
      if (annule) return;
      const tr = Array.isArray(liste) ? liste : [];
      setTroncons(tr);
      setTronconId(tr[0]?.id ?? null);
    }).catch(() => {});
    return () => { annule = true; };
  }, []);

  useEffect(() => {
    if (tronconId === null) return;
    let annule = false;
    setChargement(true);
    setErreur(null);
    setSegments(null);
    Promise.all([
      api.resumePrediction(tronconId),
      api.segmentsResumeTroncon(tronconId),
    ])
      .then(([r, s]) => {
        if (annule) return;
        setResume(r);
        setSegments(s);
      })
      .catch((e) => { if (!annule) setErreur(e instanceof Error ? e.message : String(e)); })
      .finally(() => { if (!annule) setChargement(false); });
    return () => { annule = true; };
  }, [tronconId]);

  // Calculs GPX filtrés par période
  const sessionsTout = segments?.sessions ?? [];
  const sessionsSemaine = filtrerSessions(sessionsTout, lundiSemaine());
  const sessionsMois = filtrerSessions(sessionsTout, premierDuMois());

  const statsTout = statsFromSessions(sessionsTout);
  const statsSemaine = statsFromSessions(sessionsSemaine);
  const statsMois = statsFromSessions(sessionsMois);

  const hasGpx = sessionsTout.length > 0;

  return (
    <div className="flex flex-col gap-fluid-4">
      <PageHeader
        titre="Temps de traversée par période"
        sousTitre="Temps réel basé sur Google Maps — confrontation avec les temps terrain GPX en bas de page."
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

      {!chargement && (
        <>
          {/* ═══════════════════════════════════════════════════════════════
              SECTION 1 — GOOGLE MAPS (TEMPS RÉEL) — EN HAUT
          ═══════════════════════════════════════════════════════════════ */}
          {resume && (
            <div className="flex flex-col gap-4">
              {/* Temps actuel */}
              <section className="paa-card p-fluid-4">
                <h2 className="text-fluid-base font-bold text-paa-navy-800 dark:text-paa-blue-100 mb-2">
                  Temps réel (Google Maps)
                </h2>
                <div className="flex flex-wrap gap-2 mb-3">
                  <BadgeSource source={resume.courante.source} />
                </div>
                <div className="grid gap-3 md:grid-cols-3">
                  <KpiMn label="Min" mn={resume.courante.prediction.min_mn} couleur="#2ECC71" />
                  <KpiMn label="Moyen" mn={resume.courante.prediction.moyen_mn} couleur="#3498DB" dominante />
                  <KpiMn label="Max" mn={resume.courante.prediction.max_mn} couleur="#E74C3C" />
                </div>
              </section>

              {/* Ce mois Google */}
              <section className="paa-card p-fluid-4">
                <h2 className="text-fluid-base font-bold text-paa-navy-800 dark:text-paa-blue-100 mb-1">
                  Ce mois — Google Maps
                  <span className="ml-2 text-fluid-xs font-normal app-text-muted">
                    {resume.mois.nb_mesures_total} mesure{resume.mois.nb_mesures_total !== 1 ? "s" : ""}
                  </span>
                </h2>
                <div className="grid gap-3 md:grid-cols-2">
                  <BlocTypeJour titre="Jours ouvrables (lun–ven)" stats={resume.mois.jours_ouvrables} />
                  <BlocTypeJour titre="Week-ends (sam–dim)" stats={resume.mois.week_ends} />
                </div>
              </section>

              {/* Cette semaine Google */}
              <section className="paa-card p-fluid-4">
                <h2 className="text-fluid-base font-bold text-paa-navy-800 dark:text-paa-blue-100 mb-1">
                  Cette semaine — Google Maps
                  <span className="ml-2 text-fluid-xs font-normal app-text-muted">
                    {resume.semaine.nb_mesures_total} mesure{resume.semaine.nb_mesures_total !== 1 ? "s" : ""}
                  </span>
                </h2>
                <div className="grid gap-3 md:grid-cols-2">
                  <BlocTypeJour titre="Jours ouvrables (lun–ven)" stats={resume.semaine.jours_ouvrables} />
                  <BlocTypeJour titre="Week-ends (sam–dim)" stats={resume.semaine.week_ends} />
                </div>
              </section>
            </div>
          )}

          {/* ═══════════════════════════════════════════════════════════════
              SECTION 2 — TERRAIN GPX (CONFRONTATION) — EN BAS
          ═══════════════════════════════════════════════════════════════ */}
          <div className="rounded-md border-2 border-paa-navy-300 dark:border-paa-navy-600 p-fluid-4 flex flex-col gap-4 bg-paa-blue-50 dark:bg-paa-navy-900">
            <div className="flex items-center gap-2">
              <span className="text-fluid-base font-bold text-paa-navy-800 dark:text-paa-blue-100">
                Confrontation — Terrain mesuré (GPX)
              </span>
              {hasGpx && (
                <BarreConfianceInline confiance={segments!.confiance} />
              )}
            </div>
            <p className="text-fluid-xs app-text-muted -mt-2">
              Temps réellement parcourus en voiture — à comparer avec les valeurs Google Maps ci-dessus.
            </p>

            {!hasGpx ? (
              <div className="rounded-md border app-border bg-white dark:bg-paa-navy-800 px-4 py-3 text-fluid-sm app-text-muted">
                Aucune session terrain importée — importez des fichiers GPX via la page <strong>Fiabilité</strong>.
              </div>
            ) : (
              <div className="grid gap-4 md:grid-cols-3">
                <BlocGpx
                  titre="Toutes sessions"
                  sousTitre={`${sessionsTout.length} session${sessionsTout.length > 1 ? "s" : ""} — ${formaterDate(sessionsTout[sessionsTout.length - 1].date_session)} → ${formaterDate(sessionsTout[0].date_session)}`}
                  stats={statsTout}
                />
                <BlocGpx
                  titre="Ce mois"
                  sousTitre={sessionsMois.length > 0
                    ? `${sessionsMois.length} session${sessionsMois.length > 1 ? "s" : ""} depuis le ${formaterDate(premierDuMois())}`
                    : "Aucune session ce mois"}
                  stats={statsMois}
                  vide={sessionsMois.length === 0}
                />
                <BlocGpx
                  titre="Cette semaine"
                  sousTitre={sessionsSemaine.length > 0
                    ? `${sessionsSemaine.length} session${sessionsSemaine.length > 1 ? "s" : ""} depuis le ${formaterDate(lundiSemaine())}`
                    : "Aucune session cette semaine"}
                  stats={statsSemaine}
                  vide={sessionsSemaine.length === 0}
                />
              </div>
            )}

            {hasGpx && (
              <p className="text-fluid-xs app-text-muted">
                Confiance {Math.round(segments!.confiance * 100)} % — couverture moy. {segments!.couverture_moyenne_pct.toFixed(0)} % du tronçon sur {segments!.nb_sessions} session{segments!.nb_sessions > 1 ? "s" : ""}.
                La précision s&apos;améliore automatiquement à chaque import GPX.
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sous-composants
// ---------------------------------------------------------------------------

function BlocGpx({
  titre,
  sousTitre,
  stats,
  vide = false,
}: {
  titre: string;
  sousTitre: string;
  stats: { min: number; moyen: number; max: number } | null;
  vide?: boolean;
}) {
  return (
    <div className="rounded-md border app-border p-4 app-surface flex flex-col gap-2">
      <div className="font-semibold text-fluid-sm text-paa-navy-800 dark:text-paa-blue-100">{titre}</div>
      <div className="text-fluid-xs app-text-muted">{sousTitre}</div>
      {vide || stats === null ? (
        <p className="text-fluid-xs app-text-muted italic mt-1">—</p>
      ) : (
        <div className="grid grid-cols-3 gap-1 text-center mt-1">
          <div>
            <div className="text-fluid-xs app-text-muted">Min</div>
            <div className="text-fluid-lg font-bold text-statut-fluide">{formaterMn(stats.min)}</div>
          </div>
          <div>
            <div className="text-fluid-xs app-text-muted">Moyen</div>
            <div className="text-fluid-lg font-bold text-paa-blue-500">{formaterMn(stats.moyen)}</div>
          </div>
          <div>
            <div className="text-fluid-xs app-text-muted">Max</div>
            <div className="text-fluid-lg font-bold text-statut-congestionne">{formaterMn(stats.max)}</div>
          </div>
        </div>
      )}
    </div>
  );
}

function BarreConfianceInline({ confiance }: { confiance: number }) {
  const pct = Math.round(confiance * 100);
  const couleur = pct >= 75 ? "text-statut-fluide" : pct >= 40 ? "text-yellow-500" : "text-statut-congestionne";
  return (
    <span className={`text-fluid-xs font-medium ${couleur}`}>
      {pct === 0 ? "en cours d'accumulation" : `confiance ${pct} %`}
    </span>
  );
}

function KpiMn({ label, mn, couleur, dominante = false }: { label: string; mn: number | null; couleur: string; dominante?: boolean }) {
  return (
    <div className="paa-card p-3" style={dominante ? { borderLeft: `4px solid ${couleur}` } : undefined}>
      <div className="text-fluid-xs font-medium app-text-muted">{label}</div>
      <div className="mt-1 text-fluid-xl font-bold" style={{ color: couleur }}>
        {mn === null ? "—" : `${mn} min`}
      </div>
    </div>
  );
}

function BlocTypeJour({ titre, stats }: { titre: string; stats: import("@/lib/types").StatsPeriode | null }) {
  return (
    <div className="paa-card p-3">
      <div className="text-fluid-xs font-semibold text-paa-navy-700 dark:text-paa-blue-100 mb-2">{titre}</div>
      {stats === null ? (
        <p className="text-fluid-xs app-text-muted italic">Aucune mesure.</p>
      ) : (
        <div className="grid grid-cols-3 gap-1 text-center">
          <div><div className="text-fluid-xs app-text-muted">Min</div><div className="font-bold text-statut-fluide">{stats.min_mn} mn</div></div>
          <div><div className="text-fluid-xs app-text-muted">Moy.</div><div className="font-bold text-paa-blue-500">{stats.moyen_mn} mn</div></div>
          <div><div className="text-fluid-xs app-text-muted">Max</div><div className="font-bold text-statut-congestionne">{stats.max_mn} mn</div></div>
        </div>
      )}
    </div>
  );
}

function BadgeSource({ source }: { source: SourcePrediction }) {
  const c = COULEUR_SOURCE[source];
  return (
    <span className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-fluid-xs font-medium"
      style={{ backgroundColor: `${c}22`, color: c, border: `1px solid ${c}` }}>
      <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: c }} />
      {LIBELLE_SOURCE[source]}
    </span>
  );
}

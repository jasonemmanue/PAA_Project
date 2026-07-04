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
import { usePlageHoraire } from "@/contexts/PlageHoraireContext";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
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

// Calcule la moyenne Google mensuelle pondérée (jours ouvrables + week-ends)
function googleMoyenMnMois(mois: ResumePrediction["mois"]): number | null {
  const jo = mois.jours_ouvrables;
  const we = mois.week_ends;
  if (!jo && !we) return null;
  if (!jo) return we!.moyen_mn;
  if (!we) return jo.moyen_mn;
  const totalMesures = jo.nb_mesures + we.nb_mesures;
  return Math.round((jo.moyen_mn * jo.nb_mesures + we.moyen_mn * we.nb_mesures) / totalMesures);
}

// Calcule l'écart entre GPX (s) et Google (mn) — retourne {delta_mn, pct, sens}
function calculerEcart(
  gpxMoyenS: number | undefined,
  googleMoyenMn: number | null,
): { deltaMn: number; pct: number; sens: "plus_long" | "plus_court" | "egal" } | null {
  if (!gpxMoyenS || !googleMoyenMn) return null;
  const gpxMn = gpxMoyenS / 60;
  const deltaMn = gpxMn - googleMoyenMn;
  const pct = (deltaMn / googleMoyenMn) * 100;
  const sens = Math.abs(deltaMn) < 0.5 ? "egal" : deltaMn > 0 ? "plus_long" : "plus_court";
  return { deltaMn, pct, sens };
}

const COULEUR_SOURCE: Record<SourcePrediction, string> = {
  google_routes: "#16a34a",
  mesures_jour_type_7j: "#3498DB",
  vitesse_ref_50kmh: "#95A5A6",
};

// ---------------------------------------------------------------------------
// Composant principal
// ---------------------------------------------------------------------------

export function PagePrediction() {
  const { t, locale } = useI18n();
  const { heureDebut, heureFin } = usePlageHoraire();

  const LIBELLE_SOURCE: Record<SourcePrediction, string> = {
    google_routes: t("prediction.sourceGoogle"),
    mesures_jour_type_7j: t("prediction.sourceProfils"),
    vitesse_ref_50kmh: t("prediction.sourceRef50"),
  };
  const [troncons, setTroncons] = useState<Troncon[]>([]);
  const [selection, setSelection] = useState<{
    tronconId: number;
    sousTronconId: number | null;
  } | null>(null);
  const tronconId = selection?.tronconId ?? null;
  const sousTronconId = selection?.sousTronconId ?? null;
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
      const idInitial = tr[0]?.id ?? null;
      if (idInitial !== null) {
        setSelection({ tronconId: idInitial, sousTronconId: null });
      }
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
      api.resumePrediction(tronconId, heureDebut, heureFin, sousTronconId),
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
  }, [tronconId, sousTronconId, heureDebut, heureFin]);

  // Calculs GPX filtrés par période
  const sessionsTout = segments?.sessions ?? [];
  const sessionsSemaine = filtrerSessions(sessionsTout, lundiSemaine());
  const sessionsMois = filtrerSessions(sessionsTout, premierDuMois());

  const statsTout = statsFromSessions(sessionsTout);
  const statsSemaine = statsFromSessions(sessionsSemaine);
  const statsMois = statsFromSessions(sessionsMois);

  const hasGpx = sessionsTout.length > 0;

  // Écarts Google ↔ GPX (moyennes comparées)
  const googleMoyenMois = resume ? googleMoyenMnMois(resume.mois) : null;
  const googleMoyenSemaine = resume ? googleMoyenMnMois(resume.semaine) : null;
  const ecartTout = calculerEcart(statsTout?.moyen, googleMoyenMois);
  const ecartMois = calculerEcart(statsMois?.moyen, googleMoyenMois);
  const ecartSemaine = calculerEcart(statsSemaine?.moyen, googleMoyenSemaine);

  return (
    <div className="flex flex-col gap-fluid-4">
      <PageHeader
        titre={t("prediction.title")}
        sousTitre={t("prediction.subtitle")}
      />

      {/* Sélecteur tronçon */}
      <Card>
        <label className="flex flex-col gap-1 text-fluid-sm font-medium max-w-md">
          {t("prediction.selectTroncon")}
          <select
            value={
              selection === null
                ? ""
                : selection.sousTronconId !== null
                  ? `sous-${selection.sousTronconId}`
                  : `axe-${selection.tronconId}`
            }
            onChange={(e) => {
              const v = e.target.value;
              if (v.startsWith("axe-")) {
                setSelection({ tronconId: Number(v.slice(4)), sousTronconId: null });
              } else if (v.startsWith("sous-")) {
                const sid = Number(v.slice(5));
                const parent = troncons.find((a) =>
                  (a.sous_troncons ?? []).some((s) => s.id === sid),
                );
                if (parent) setSelection({ tronconId: parent.id, sousTronconId: sid });
              }
            }}
            className="rounded-md border app-border app-surface px-3 py-2 text-fluid-base
                       focus:outline-none focus:ring-2 focus:ring-paa-blue-400 min-h-[42px]"
          >
            <optgroup label="── Axes ──">
              {troncons.map((tr) => (
                <option key={`axe-${tr.id}`} value={`axe-${tr.id}`}>{tr.nom}</option>
              ))}
            </optgroup>
            {troncons.some((t) => (t.sous_troncons?.length ?? 0) > 0) && (
              <optgroup label="── Tronçons par axes ──">
                {troncons.flatMap((a) =>
                  (a.sous_troncons ?? []).map((s) => (
                    <option key={`sous-${s.id}`} value={`sous-${s.id}`}>
                      {a.nom} : {s.nom_court} ({s.code})
                    </option>
                  )),
                )}
              </optgroup>
            )}
          </select>
        </label>
      </Card>

      {erreur && (
        <div className="rounded-md bg-statut-congestionne/10 border border-statut-congestionne/40 px-3 py-2 text-fluid-sm text-statut-congestionne">
          {t("prediction.erreur")} {erreur}
        </div>
      )}
      {chargement && (
        <div className="text-fluid-sm app-text-muted animate-pulse">{t("prediction.chargement")}</div>
      )}

      {!chargement && (
        <>
          {/* ═══════════════════════════════════════════════════════════════
              SECTION 1 — GOOGLE MAPS (TEMPS RÉEL) — EN HAUT
          ═══════════════════════════════════════════════════════════════ */}
          {resume && (
            <div className="flex flex-col gap-4">
              {/* ── Bloc principal : Min / Moy / Max — dynamique selon source ── */}
              <section className="paa-card p-fluid-4">
                {(() => {
                  const h = parseInt(
                    new Intl.DateTimeFormat("fr-FR", {
                      hour: "2-digit",
                      hour12: false,
                      timeZone: "Africa/Abidjan",
                    }).format(new Date()),
                    10,
                  );
                  const minutes = new Date().getMinutes();
                  const isGoogle = resume.courante.source === "google_routes";
                  const hPrev = h === 0 ? 23 : h - 1;
                  const creneauPrecLabel = `${hPrev}h – ${h}h`;
                  const creneauActuelLabel = `${h}h – ${h + 1}h`;

                  const tj = resume.courante.type_jour;
                  const estOuvrable = tj === "jour_ouvrable";
                  const typeJourLabel = estOuvrable
                    ? (locale === "fr" ? "jours ouvrables" : "weekdays")
                    : (locale === "fr" ? "week-ends" : "weekends");

                  const semStats = estOuvrable ? resume.semaine.jours_ouvrables : resume.semaine.week_ends;
                  const moisStats = estOuvrable ? resume.mois.jours_ouvrables : resume.mois.week_ends;
                  const fallback = (semStats?.nb_mesures ?? 0) >= 2 ? semStats : moisStats;
                  const minMn = resume.courante.bornes_7j?.min_mn
                    ?? fallback?.min_mn
                    ?? resume.courante.prediction.min_mn;
                  const moyMn = resume.courante.prediction.moyen_mn;
                  const maxMn = resume.courante.bornes_7j?.max_mn
                    ?? fallback?.max_mn
                    ?? resume.courante.prediction.max_mn;

                  return (
                    <>
                      <div className="flex items-center justify-between mb-4">
                        <h2 className="text-fluid-base font-bold text-paa-navy-800 dark:text-paa-blue-100">
                          {t("prediction.tempsReel")}
                        </h2>
                        <BadgeSource source={resume.courante.source} libelleSource={LIBELLE_SOURCE} />
                      </div>

                      {/* Explication dynamique de la source des données */}
                      <div className="mb-4 rounded-lg border app-border bg-slate-50 dark:bg-slate-900/40 px-4 py-2.5">
                        {isGoogle ? (
                          <div className="flex items-start gap-2">
                            <span className="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-green-500 animate-pulse" />
                            <div>
                              <p className="text-fluid-xs font-semibold text-paa-navy-800 dark:text-paa-blue-100">
                                {locale === "fr"
                                  ? `Mesure Google Maps du créneau ${creneauPrecLabel}`
                                  : `Google Maps measurement from slot ${creneauPrecLabel}`}
                              </p>
                              <p className="text-[11px] app-text-muted mt-0.5">
                                {locale === "fr"
                                  ? `La moyenne (Moy.) est la mesure réelle Google. Le Min et le Max sont issus de ce même créneau horaire sur les 7 derniers ${typeJourLabel}.`
                                  : `Average (Avg.) is the actual Google measurement. Min and Max come from this same time slot over the last 7 ${typeJourLabel}.`}
                              </p>
                            </div>
                          </div>
                        ) : (
                          <div className="flex items-start gap-2">
                            <span className="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-blue-500" />
                            <div>
                              <p className="text-fluid-xs font-semibold text-paa-navy-800 dark:text-paa-blue-100">
                                {locale === "fr"
                                  ? `Moyenne des 7 derniers ${typeJourLabel} sur le créneau ${creneauActuelLabel}`
                                  : `Average of the last 7 ${typeJourLabel} on slot ${creneauActuelLabel}`}
                              </p>
                              <p className="text-[11px] app-text-muted mt-0.5">
                                {locale === "fr"
                                  ? `Aucune mesure Google dans les 15 dernières minutes. Min, Moy. et Max sont calculés à partir des mesures collectées sur ce créneau horaire durant les 7 derniers ${typeJourLabel}.`
                                  : `No Google measurement in the last 15 minutes. Min, Avg., and Max are computed from measurements collected on this time slot over the last 7 ${typeJourLabel}.`}
                              </p>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Min / Moy / Max */}
                      <div className="grid grid-cols-3 gap-3 max-w-lg mx-auto text-center">
                        <div className="rounded-lg border app-border p-3 bg-green-50/50 dark:bg-green-950/10">
                          <div className="text-[10px] font-semibold uppercase tracking-wider text-green-600 dark:text-green-400 mb-1">
                            {t("prediction.labelMin")}
                          </div>
                          <div className="text-fluid-xl font-bold text-green-700 dark:text-green-300">
                            {minMn ?? "—"}
                            <span className="text-fluid-xs font-medium ml-0.5">min</span>
                          </div>
                          <div className="text-[9px] app-text-muted mt-1">
                            {locale === "fr" ? `7 dern. ${typeJourLabel}` : `last 7 ${typeJourLabel}`}
                          </div>
                        </div>
                        <div className="rounded-lg border-2 border-paa-blue-300 dark:border-paa-blue-600 p-3 bg-paa-blue-50/50 dark:bg-slate-800/60 shadow-sm">
                          <div className="text-[10px] font-semibold uppercase tracking-wider text-paa-blue-600 dark:text-paa-blue-300 mb-1">
                            {t("prediction.labelMoy")}
                          </div>
                          <div className="text-[32px] font-extrabold leading-none text-paa-navy-800 dark:text-paa-blue-50">
                            {moyMn ?? "—"}
                            <span className="text-fluid-sm font-semibold ml-0.5 text-paa-navy-500 dark:text-paa-blue-300">min</span>
                          </div>
                          <div className="text-[9px] app-text-muted mt-1">
                            {isGoogle
                              ? (locale === "fr" ? "mesure Google" : "Google measurement")
                              : (locale === "fr" ? `7 dern. ${typeJourLabel}` : `last 7 ${typeJourLabel}`)}
                          </div>
                        </div>
                        <div className="rounded-lg border app-border p-3 bg-red-50/50 dark:bg-red-950/10">
                          <div className="text-[10px] font-semibold uppercase tracking-wider text-red-600 dark:text-red-400 mb-1">
                            {t("prediction.labelMax")}
                          </div>
                          <div className="text-fluid-xl font-bold text-red-700 dark:text-red-300">
                            {maxMn ?? "—"}
                            <span className="text-fluid-xs font-medium ml-0.5">min</span>
                          </div>
                          <div className="text-[9px] app-text-muted mt-1">
                            {locale === "fr" ? `7 dern. ${typeJourLabel}` : `last 7 ${typeJourLabel}`}
                          </div>
                        </div>
                      </div>

                      {/* Pastille type de jour */}
                      <div className="mt-3 flex justify-center">
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100
                                         dark:bg-slate-800 px-3 py-1 text-[10px] font-medium
                                         text-slate-600 dark:text-slate-300">
                          <span className="h-1.5 w-1.5 rounded-full bg-paa-blue-400" />
                          {locale === "fr"
                            ? `Aujourd'hui est un ${estOuvrable ? "jour ouvrable" : "jour de week-end"} — Min/Max issus des 7 derniers ${typeJourLabel}`
                            : `Today is a ${estOuvrable ? "weekday" : "weekend day"} — Min/Max from the last 7 ${typeJourLabel}`}
                        </span>
                      </div>
                    </>
                  );
                })()}
              </section>

              {/* ── Bloc inférieur : Créneau horaire précédent ── */}
              <section className="paa-card p-fluid-4 bg-slate-50 dark:bg-slate-900/30">
                {(() => {
                  const h = parseInt(
                    new Intl.DateTimeFormat("fr-FR", {
                      hour: "2-digit",
                      hour12: false,
                      timeZone: "Africa/Abidjan",
                    }).format(new Date()),
                    10,
                  );
                  const hPrev = h === 0 ? 23 : h - 1;
                  const creneauPrecLabel = `${hPrev}h – ${h}h`;
                  const creneauActuelLabel = `${h}h – ${h + 1}h`;
                  const isGoogle = resume.courante.source === "google_routes";

                  return (
                    <div className="flex items-center gap-4">
                      <div className="flex-shrink-0 flex items-center justify-center h-14 w-14
                                      rounded-full bg-paa-blue-100 dark:bg-paa-navy-700
                                      border-2 border-paa-blue-300 dark:border-paa-blue-500">
                        <span className="text-fluid-base font-bold text-paa-navy-700 dark:text-paa-blue-100 leading-tight text-center">
                          {resume.courante.prediction.moyen_mn != null
                            ? <><span className="text-lg">{resume.courante.prediction.moyen_mn}</span><br /><span className="text-[10px]">min</span></>
                            : "—"}
                        </span>
                      </div>
                      <div className="flex-1">
                        <p className="text-fluid-xs font-semibold text-paa-navy-800 dark:text-paa-blue-100">
                          {locale === "fr"
                            ? `Temps du créneau précédent : ${creneauPrecLabel}`
                            : `Previous slot time: ${creneauPrecLabel}`}
                        </p>
                        <p className="text-[11px] app-text-muted mt-0.5">
                          {locale === "fr"
                            ? `Cette mesure est utilisée comme référence durant les 15 premières minutes du créneau suivant (${creneauActuelLabel}), avant qu'une nouvelle mesure Google ne soit collectée.`
                            : `This measurement is used as reference during the first 15 minutes of the next slot (${creneauActuelLabel}), before a new Google measurement is collected.`}
                        </p>
                      </div>
                    </div>
                  );
                })()}
              </section>

              {/* Cette semaine Google — ordre chronologique : semaine d'abord */}
              <section className="paa-card p-fluid-4">
                <h2 className="text-fluid-base font-bold text-paa-navy-800 dark:text-paa-blue-100 mb-1">
                  {t("prediction.cetteSemaine")}
                  <span className="ml-2 text-fluid-xs font-normal app-text-muted">
                    {resume.semaine.nb_mesures_total} {resume.semaine.nb_mesures_total !== 1 ? t("prediction.mesures") : t("prediction.mesure")}
                  </span>
                </h2>
                <div className="grid gap-3 md:grid-cols-2">
                  <BlocTypeJour titre={t("prediction.joursOuvrables")} labelMin={t("prediction.labelMin")} labelMoy={t("prediction.labelMoy")} labelMax={t("prediction.labelMax")} unite={t("prediction.uniteMn")} stats={resume.semaine.jours_ouvrables} />
                  <BlocTypeJour titre={t("prediction.weekEnds")} labelMin={t("prediction.labelMin")} labelMoy={t("prediction.labelMoy")} labelMax={t("prediction.labelMax")} unite={t("prediction.uniteMn")} stats={resume.semaine.week_ends} />
                </div>
              </section>

              {/* Ce mois Google — englobe la semaine */}
              <section className="paa-card p-fluid-4">
                <h2 className="text-fluid-base font-bold text-paa-navy-800 dark:text-paa-blue-100 mb-1">
                  {t("prediction.ceMois")}
                  <span className="ml-2 text-fluid-xs font-normal app-text-muted">
                    {resume.mois.nb_mesures_total} {resume.mois.nb_mesures_total !== 1 ? t("prediction.mesures") : t("prediction.mesure")}
                  </span>
                </h2>
                <div className="grid gap-3 md:grid-cols-2">
                  <BlocTypeJour titre={t("prediction.joursOuvrables")} labelMin={t("prediction.labelMin")} labelMoy={t("prediction.labelMoy")} labelMax={t("prediction.labelMax")} unite={t("prediction.uniteMn")} stats={resume.mois.jours_ouvrables} />
                  <BlocTypeJour titre={t("prediction.weekEnds")} labelMin={t("prediction.labelMin")} labelMoy={t("prediction.labelMoy")} labelMax={t("prediction.labelMax")} unite={t("prediction.uniteMn")} stats={resume.mois.week_ends} />
                </div>
              </section>
            </div>
          )}

          {/* ═══════════════════════════════════════════════════════════════
              BANDEAU ÉCART — visible seulement si Google + GPX disponibles
          ═══════════════════════════════════════════════════════════════ */}
          {hasGpx && ecartTout && (
            <BandeauEcart ecart={ecartTout} label={t("prediction.ecartLabel")} t={t} />
          )}

          {/* ═══════════════════════════════════════════════════════════════
              SECTION 2 — TERRAIN GPX (CONFRONTATION) — EN BAS
          ═══════════════════════════════════════════════════════════════ */}
          <div className="rounded-md border-2 border-paa-navy-300 dark:border-paa-navy-600 p-fluid-4 flex flex-col gap-4 bg-paa-blue-50 dark:bg-paa-navy-900">
            <div className="flex items-center gap-2">
              <span className="text-fluid-base font-bold text-paa-navy-800 dark:text-paa-blue-100">
                {t("prediction.confrontationTitre")}
              </span>
              {hasGpx && (
                <BarreConfianceInline confiance={segments!.confiance} t={t} />
              )}
            </div>
            <p className="text-fluid-xs app-text-muted -mt-2">
              {t("prediction.confrontationDesc")}
            </p>

            {!hasGpx ? (
              <div className="rounded-md border app-border bg-white dark:bg-paa-navy-800 px-4 py-3 text-fluid-sm app-text-muted">
                {t("prediction.aucuneSessionImport")} <strong>{t("prediction.fiabilite")}</strong>.
              </div>
            ) : (
              <div className="grid gap-4 md:grid-cols-3">
                <BlocGpx
                  titre={t("prediction.toutesSessionsTitre")}
                  sousTitre={`${sessionsTout.length} ${sessionsTout.length > 1 ? t("prediction.sessions") : t("prediction.session")} — ${formaterDate(sessionsTout[sessionsTout.length - 1].date_session)} → ${formaterDate(sessionsTout[0].date_session)}`}
                  stats={statsTout}
                  ecart={ecartTout}
                  t={t}
                />
                <BlocGpx
                  titre={t("prediction.cetteSemaineTitre")}
                  sousTitre={sessionsSemaine.length > 0
                    ? `${sessionsSemaine.length} ${sessionsSemaine.length > 1 ? t("prediction.sessions") : t("prediction.session")} ${t("prediction.depuisLe")} ${formaterDate(lundiSemaine())}`
                    : t("prediction.aucuneSessionSemaine")}
                  stats={statsSemaine}
                  vide={sessionsSemaine.length === 0}
                  ecart={ecartSemaine}
                  t={t}
                />
                <BlocGpx
                  titre={t("prediction.ceMoisTitre")}
                  sousTitre={sessionsMois.length > 0
                    ? `${sessionsMois.length} ${sessionsMois.length > 1 ? t("prediction.sessions") : t("prediction.session")} ${t("prediction.depuisLe")} ${formaterDate(premierDuMois())}`
                    : t("prediction.aucuneSessionMois")}
                  stats={statsMois}
                  vide={sessionsMois.length === 0}
                  ecart={ecartMois}
                  t={t}
                />
              </div>
            )}

            {hasGpx && (
              <p className="text-fluid-xs app-text-muted">
                {t("prediction.confiancePct")} {Math.round(segments!.confiance * 100)} % — {t("prediction.couvertureMoy")} {segments!.couverture_moyenne_pct.toFixed(0)} % {t("prediction.duTroncon")} {segments!.nb_sessions} {segments!.nb_sessions > 1 ? t("prediction.sessions") : t("prediction.session")}.
                {" "}{t("prediction.precisionNote")}
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

type Ecart = ReturnType<typeof calculerEcart>;
type TFn = (key: string) => string;

function BlocGpx({
  titre, sousTitre, stats, vide = false, ecart, t,
}: {
  titre: string; sousTitre: string;
  stats: { min: number; moyen: number; max: number } | null;
  vide?: boolean; ecart?: Ecart; t: TFn;
}) {
  return (
    <div className="rounded-md border app-border p-4 app-surface flex flex-col gap-2">
      <div className="font-semibold text-fluid-sm text-paa-navy-800 dark:text-paa-blue-100">{titre}</div>
      <div className="text-fluid-xs app-text-muted">{sousTitre}</div>
      {vide || stats === null ? (
        <p className="text-fluid-xs app-text-muted italic mt-1">—</p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-1 text-center mt-1">
            <div>
              <div className="text-fluid-xs app-text-muted">{t("prediction.labelMin")}</div>
              <div className="text-fluid-lg font-bold text-statut-fluide">{formaterMn(stats.min)}</div>
            </div>
            <div>
              <div className="text-fluid-xs app-text-muted">{t("prediction.labelMoyen")}</div>
              <div className="text-fluid-lg font-bold text-paa-blue-500">{formaterMn(stats.moyen)}</div>
            </div>
            <div>
              <div className="text-fluid-xs app-text-muted">{t("prediction.labelMax")}</div>
              <div className="text-fluid-lg font-bold text-statut-congestionne">{formaterMn(stats.max)}</div>
            </div>
          </div>
          {ecart && <PuceEcart ecart={ecart} t={t} />}
        </>
      )}
    </div>
  );
}

function PuceEcart({ ecart, t }: { ecart: NonNullable<Ecart>; t: TFn }) {
  if (ecart.sens === "egal") {
    return (
      <div className="mt-1 text-center text-fluid-xs font-medium text-statut-fluide">
        {t("prediction.puceEgal")}
      </div>
    );
  }
  const positif = ecart.sens === "plus_long";
  const couleur = positif ? "text-statut-congestionne" : "text-statut-fluide";
  const bg = positif ? "bg-statut-congestionne/10 border-statut-congestionne/30" : "bg-statut-fluide/10 border-statut-fluide/30";
  const signe = positif ? "+" : "−";
  const mn = Math.abs(ecart.deltaMn);
  const mnAff = mn >= 1 ? `${Math.round(mn)} min` : `${Math.round(mn * 60)} s`;
  const pctAff = `${signe}${Math.round(Math.abs(ecart.pct))} %`;
  const libelle = positif ? t("prediction.terrainPlusLongCourt") : t("prediction.terrainPlusCourtel");

  return (
    <div className={`mt-1 rounded border px-2 py-1 text-center text-fluid-xs font-semibold ${couleur} ${bg}`}>
      {signe}{mnAff} ({pctAff}) — {libelle}
    </div>
  );
}

function BandeauEcart({ ecart, label, t }: { ecart: NonNullable<Ecart>; label: string; t: TFn }) {
  const positif = ecart.sens === "plus_long";
  const egal = ecart.sens === "egal";
  const bgClass = egal
    ? "bg-paa-blue-50 dark:bg-paa-navy-800 border-paa-navy-200 dark:border-paa-navy-600"
    : positif
    ? "bg-statut-congestionne/10 border-statut-congestionne/40"
    : "bg-statut-fluide/10 border-statut-fluide/40";
  const textClass = egal
    ? "text-paa-navy-600 dark:text-paa-blue-200"
    : positif
    ? "text-statut-congestionne"
    : "text-statut-fluide";

  const mn = Math.abs(ecart.deltaMn);
  const mnAff = mn >= 1 ? `${Math.round(mn)} min` : `${Math.round(mn * 60)} s`;
  const pctAff = `${Math.round(Math.abs(ecart.pct))} %`;

  const message = egal
    ? t("prediction.ecartEgal")
    : positif
    ? `${t("prediction.terrainPlusLong")} ${mnAff} (${pctAff}) ${t("prediction.ecartPlusLong")}`
    : `${t("prediction.terrainPlusCourt")} ${mnAff} (${pctAff}) ${t("prediction.ecartPlusCourt")}`;

  return (
    <div className={`rounded-md border px-4 py-3 flex items-center gap-3 ${bgClass}`}>
      <span className={`text-fluid-xl ${textClass}`}>{egal ? "≈" : positif ? "▲" : "▼"}</span>
      <div>
        <div className={`text-fluid-sm font-bold ${textClass}`}>{t("prediction.ecartTitre")}</div>
        <div className={`text-fluid-xs ${textClass} opacity-80`}>{message}</div>
        <div className="text-fluid-xs app-text-muted mt-0.5">{label}</div>
      </div>
    </div>
  );
}

function BarreConfianceInline({ confiance, t }: { confiance: number; t: TFn }) {
  const pct = Math.round(confiance * 100);
  const couleur = pct >= 75 ? "text-statut-fluide" : pct >= 40 ? "text-yellow-500" : "text-statut-congestionne";
  return (
    <span className={`text-fluid-xs font-medium ${couleur}`}>
      {pct === 0 ? t("prediction.precisionNote") : `${t("prediction.confiancePct")} ${pct} %`}
    </span>
  );
}

function KpiMn({ label, mn, couleur, dominante = false }: { label: string; mn: number | null; couleur: string; dominante?: boolean; }) {
  return (
    <div className="paa-card p-3" style={dominante ? { borderLeft: `4px solid ${couleur}` } : undefined}>
      <div className="text-fluid-xs font-medium app-text-muted">{label}</div>
      <div className="mt-1 text-fluid-xl font-bold" style={{ color: couleur }}>
        {mn === null ? "—" : `${mn} min`}
      </div>
    </div>
  );
}

function BlocTypeJour({ titre, stats, labelMin, labelMoy, labelMax, unite }: {
  titre: string; stats: import("@/lib/types").StatsPeriode | null;
  labelMin: string; labelMoy: string; labelMax: string; unite: string;
}) {
  return (
    <div className="paa-card p-3">
      <div className="text-fluid-xs font-semibold text-paa-navy-700 dark:text-paa-blue-100 mb-2">{titre}</div>
      {stats === null ? (
        <p className="text-fluid-xs app-text-muted italic">—</p>
      ) : (
        <div className="grid grid-cols-3 gap-1 text-center">
          <div><div className="text-fluid-xs app-text-muted">{labelMin}</div><div className="font-bold text-statut-fluide">{stats.min_mn} {unite}</div></div>
          <div><div className="text-fluid-xs app-text-muted">{labelMoy}</div><div className="font-bold text-paa-blue-500">{stats.moyen_mn} {unite}</div></div>
          <div><div className="text-fluid-xs app-text-muted">{labelMax}</div><div className="font-bold text-statut-congestionne">{stats.max_mn} {unite}</div></div>
        </div>
      )}
    </div>
  );
}

function BadgeSource({ source, libelleSource }: { source: SourcePrediction; libelleSource: Record<SourcePrediction, string> }) {
  const c = COULEUR_SOURCE[source];
  return (
    <span className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-fluid-xs font-medium"
      style={{ backgroundColor: `${c}22`, color: c, border: `1px solid ${c}` }}>
      <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: c }} />
      {libelleSource[source]}
    </span>
  );
}

function CascadeNiveau({ niveau, actif, libelle, confiance, couleur }: {
  niveau: number; actif: boolean; libelle: string; confiance: string; couleur: string;
}) {
  return (
    <div className={`flex items-center gap-2 rounded-md px-3 py-2 text-fluid-xs transition-all ${
      actif
        ? "border-2 font-semibold shadow-sm"
        : "border border-dashed opacity-50"
    }`}
      style={actif ? { borderColor: couleur, backgroundColor: `${couleur}11` } : undefined}
    >
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-white text-[10px] font-bold"
            style={{ backgroundColor: actif ? couleur : "#CBD5E1" }}>
        {niveau}
      </span>
      <span className="flex-1">{libelle}</span>
      <span className="font-mono text-fluid-xs" style={{ color: actif ? couleur : undefined }}>
        {actif ? `✓ ${confiance}` : confiance}
      </span>
    </div>
  );
}

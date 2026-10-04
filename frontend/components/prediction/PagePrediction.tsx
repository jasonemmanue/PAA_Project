"use client";

/**
 * Page Temps de traversée par période — mesures Google Maps uniquement.
 *
 * Blocs :
 *   1. Temps actuel (mesure Google du créneau courant) + min/moy/max sur
 *      les 7 derniers jours du même type de jour
 *   2. Cette semaine — jours ouvrables / week-ends
 *   3. Ce mois       — jours ouvrables / week-ends
 *
 * La confrontation avec les relevés GPX terrain a été retirée de cette page
 * (2026-10-04) : elle reste consultable sur la page Fiabilité.
 */

import { useEffect, useState } from "react";

import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { usePlageHoraire } from "@/contexts/PlageHoraireContext";
import { api } from "@/lib/api";
import { formaterDuree } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type {
  PlageCollecte,
  ResumePrediction,
  SourcePrediction,
  Troncon,
} from "@/lib/types";

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
  const [plageCollecte, setPlageCollecte] = useState<PlageCollecte | null>(null);
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
    api.plageCollecte().then((p) => { if (!annule) setPlageCollecte(p); }).catch(() => {});
    return () => { annule = true; };
  }, []);

  useEffect(() => {
    if (tronconId === null) return;
    let annule = false;

    const charger = () => {
      api.resumePrediction(tronconId, heureDebut, heureFin, sousTronconId)
        .then((r) => {
          if (!annule) setResume(r);
        })
        .catch((e) => { if (!annule) setErreur(e instanceof Error ? e.message : String(e)); })
        .finally(() => { if (!annule) setChargement(false); });
    };

    setChargement(true);
    setErreur(null);
    charger();

    // Rafraîchissement automatique toutes les 5 min — les données Google et les
    // week-ends apparaissent sans rechargement manuel de la page.
    const intervalle = setInterval(charger, 5 * 60 * 1000);
    return () => { annule = true; clearInterval(intervalle); };
  }, [tronconId, sousTronconId, heureDebut, heureFin]);

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
            value={selection === null ? "" : String(selection.tronconId)}
            onChange={(e) => {
              setSelection({ tronconId: Number(e.target.value), sousTronconId: null });
            }}
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
          {t("prediction.erreur")} {erreur}
        </div>
      )}
      {chargement && (
        <div className="text-fluid-sm app-text-muted animate-pulse">{t("prediction.chargement")}</div>
      )}

      {!chargement && (
        <>
          {/* ═══════════════════════════════════════════════════════════════
              SECTION 1 — PLAGE DE TEMPS GOOGLE MAPS — EN HAUT
          ═══════════════════════════════════════════════════════════════ */}
          {resume && (
            <div className="flex flex-col gap-4">
              {/* ── Bloc principal : Nom de l'axe + plage horaire + Min/Moy/Max ── */}
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
                  const creneauLabel = `${h}h – ${h + 1}h`;
                  const horsPlage = plageCollecte !== null
                    && (h < plageCollecte.heure_debut || h >= plageCollecte.heure_fin);

                  const tj = resume.courante.type_jour;
                  const estOuvrable = tj === "jour_ouvrable";
                  const typeJourLabel = estOuvrable
                    ? (locale === "fr" ? "jours ouvrables" : "weekdays")
                    : (locale === "fr" ? "week-ends" : "weekends");

                  const bornes = resume.courante.bornes_7j;
                  // fallback sur les stats semaine / mois si bornes_7j et prediction sont null
                  const fallbackJo = estOuvrable ? resume.semaine.jours_ouvrables : resume.semaine.week_ends;
                  const fallbackMois = estOuvrable ? resume.mois.jours_ouvrables : resume.mois.week_ends;
                  const minS = bornes?.min_s
                    ?? resume.courante.prediction.min_s
                    ?? (fallbackJo?.min_s ?? (fallbackJo?.min_mn != null ? Math.round(fallbackJo.min_mn * 60) : null))
                    ?? (fallbackMois?.min_s ?? (fallbackMois?.min_mn != null ? Math.round(fallbackMois.min_mn * 60) : null));
                  const moyS = bornes?.moyen_s
                    ?? resume.courante.prediction.moyen_s
                    ?? (fallbackJo?.moyen_s ?? (fallbackJo?.moyen_mn != null ? Math.round(fallbackJo.moyen_mn * 60) : null))
                    ?? (fallbackMois?.moyen_s ?? (fallbackMois?.moyen_mn != null ? Math.round(fallbackMois.moyen_mn * 60) : null));
                  const maxS = bornes?.max_s
                    ?? resume.courante.prediction.max_s
                    ?? (fallbackJo?.max_s ?? (fallbackJo?.max_mn != null ? Math.round(fallbackJo.max_mn * 60) : null))
                    ?? (fallbackMois?.max_s ?? (fallbackMois?.max_mn != null ? Math.round(fallbackMois.max_mn * 60) : null));
                  const noteSource = bornes
                    ? (locale === "fr" ? `7 derniers ${typeJourLabel}` : `last 7 ${typeJourLabel}`)
                    : (fallbackJo?.nb_mesures ?? 0) > 0
                      ? (locale === "fr" ? `semaine en cours — ${typeJourLabel}` : `current week — ${typeJourLabel}`)
                      : (fallbackMois?.nb_mesures ?? 0) > 0
                        ? (locale === "fr" ? `mois en cours — ${typeJourLabel}` : `current month — ${typeJourLabel}`)
                        : (locale === "fr" ? "référence 50 km/h" : "50 km/h reference");

                  return (
                    <>
                      {/* Nom de l'axe en gros */}
                      <div className="text-center mb-3">
                        <h2 className="text-fluid-lg font-extrabold text-paa-navy-800 dark:text-paa-blue-50 leading-tight">
                          {resume.troncon_nom}
                        </h2>
                        <div className="mt-1 inline-flex items-center gap-2 rounded-full bg-paa-blue-100 dark:bg-paa-navy-700 px-4 py-1.5">
                          <span className="h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
                          <span className="text-fluid-sm font-bold text-paa-navy-700 dark:text-paa-blue-100">
                            {t("prediction.tempsReel")} — {creneauLabel}
                          </span>
                        </div>
                      </div>

                      {/* Bande temps actuel — mesure Google brute du créneau courant uniquement */}
                      <div className={`mb-4 rounded-xl border-2 p-4 text-center ${
                        resume.courante.mesure_creneau_actuel
                          ? "border-green-400 dark:border-green-600 bg-green-50/60 dark:bg-green-950/20"
                          : "border-slate-200 dark:border-slate-700 bg-slate-50/40 dark:bg-slate-800/20"
                      }`}>
                        <div className={`text-[11px] font-semibold uppercase tracking-wider mb-1 ${
                          resume.courante.mesure_creneau_actuel
                            ? "text-green-600 dark:text-green-400"
                            : "text-slate-400 dark:text-slate-500"
                        }`}>
                          {locale === "fr"
                            ? `Temps actuel — ${creneauLabel}`
                            : `Current time — ${creneauLabel}`}
                        </div>
                        {resume.courante.mesure_creneau_actuel ? (
                          <>
                            <div className="text-[42px] font-black leading-none text-green-700 dark:text-green-300">
                              {formaterDuree(resume.courante.mesure_creneau_actuel.duree_s)}
                            </div>
                            <div className="mt-1 inline-flex items-center gap-1.5 text-[10px] text-green-600 dark:text-green-400">
                              <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
                              {LIBELLE_SOURCE["google_routes"]}
                            </div>
                          </>
                        ) : (
                          <div className="py-2 text-[16px] font-medium text-slate-400 dark:text-slate-500">
                            {horsPlage
                              ? (locale === "fr"
                                ? `Hors plage de collecte (${plageCollecte!.heure_debut}h – ${plageCollecte!.heure_fin}h)`
                                : `Outside collection window (${plageCollecte!.heure_debut}h – ${plageCollecte!.heure_fin}h)`)
                              : (locale === "fr"
                                ? "En attente de mesure Google Maps"
                                : "Awaiting Google Maps measurement")}
                          </div>
                        )}
                      </div>

                      {/* Note source des statistiques MIN / MOY / MAX */}
                      <div className="mb-4 rounded-lg border app-border bg-slate-50 dark:bg-slate-900/40 px-4 py-2.5">
                        <div className="flex items-start gap-2">
                          <span className="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-blue-500" />
                          <p className="text-fluid-xs text-paa-navy-700 dark:text-paa-blue-200">
                            {locale === "fr"
                              ? `Min, Moy. et Max — ${noteSource}.`
                              : `Min, Avg. and Max — ${noteSource}.`}
                          </p>
                        </div>
                      </div>

                      {/* Min / Moy / Max — plage 7 jours */}
                      <div className="grid grid-cols-3 gap-3 max-w-lg mx-auto text-center">
                        <div className="rounded-xl border app-border p-4 bg-green-50/50 dark:bg-green-950/10">
                          <div className="text-[11px] font-semibold uppercase tracking-wider text-green-600 dark:text-green-400 mb-1">
                            {t("prediction.labelMin")}
                          </div>
                          <DureeDeuxLignes
                            s={minS}
                            classMin="text-[28px] font-bold text-green-700 dark:text-green-300"
                            classSec="text-[20px] font-semibold text-green-600 dark:text-green-400"
                          />
                        </div>
                        <div className="rounded-xl border-2 border-paa-blue-300 dark:border-paa-blue-600 p-4 bg-paa-blue-50/50 dark:bg-slate-800/60 shadow-md">
                          <div className="text-[11px] font-semibold uppercase tracking-wider text-paa-blue-600 dark:text-paa-blue-300 mb-1">
                            {t("prediction.labelMoy")}
                          </div>
                          <DureeDeuxLignes
                            s={moyS}
                            classMin="text-[36px] font-extrabold leading-none text-paa-navy-800 dark:text-paa-blue-50"
                            classSec="text-[22px] font-bold text-paa-navy-700 dark:text-paa-blue-200"
                          />
                        </div>
                        <div className="rounded-xl border app-border p-4 bg-red-50/50 dark:bg-red-950/10">
                          <div className="text-[11px] font-semibold uppercase tracking-wider text-red-600 dark:text-red-400 mb-1">
                            {t("prediction.labelMax")}
                          </div>
                          <DureeDeuxLignes
                            s={maxS}
                            classMin="text-[28px] font-bold text-red-700 dark:text-red-300"
                            classSec="text-[20px] font-semibold text-red-600 dark:text-red-400"
                          />
                        </div>
                      </div>

                      {/* Pastille type de jour */}
                      <div className="mt-3 flex justify-center">
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100
                                         dark:bg-slate-800 px-3 py-1 text-[11px] font-medium
                                         text-slate-600 dark:text-slate-300">
                          <span className="h-1.5 w-1.5 rounded-full bg-paa-blue-400" />
                          {locale === "fr"
                            ? `${estOuvrable ? "Jour ouvrable" : "Week-end"} — 7 derniers ${typeJourLabel}`
                            : `${estOuvrable ? "Weekday" : "Weekend"} — last 7 ${typeJourLabel}`}
                        </span>
                      </div>
                    </>
                  );
                })()}
              </section>

              {/* Cette semaine Google */}
              <section className="paa-card p-fluid-4">
                <h2 className="text-fluid-base font-bold text-paa-navy-800 dark:text-paa-blue-100 mb-1">
                  {t("prediction.cetteSemaine")}
                  <span className="ml-2 text-fluid-xs font-normal app-text-muted">
                    {resume.semaine.nb_mesures_total} {resume.semaine.nb_mesures_total !== 1 ? t("prediction.mesures") : t("prediction.mesure")}
                  </span>
                </h2>
                <div className="grid gap-3 md:grid-cols-2">
                  <BlocTypeJour titre={t("prediction.joursOuvrables")} labelMin={t("prediction.labelMin")} labelMoy={t("prediction.labelMoy")} labelMax={t("prediction.labelMax")} unite={t("prediction.uniteMn")} stats={resume.semaine.jours_ouvrables} />
                  <BlocTypeJour titre={t("prediction.weekEnds")} labelMin={t("prediction.labelMin")} labelMoy={t("prediction.labelMoy")} labelMax={t("prediction.labelMax")} unite={t("prediction.uniteMn")} stats={resume.semaine.week_ends}
                    messageVide={locale === "fr" ? "Pas encore de week-end cette semaine — disponible samedi" : "No weekend yet this week — available Saturday"} />
                </div>
              </section>

              {/* Ce mois Google */}
              <section className="paa-card p-fluid-4">
                <h2 className="text-fluid-base font-bold text-paa-navy-800 dark:text-paa-blue-100 mb-1">
                  {t("prediction.ceMois")}
                  <span className="ml-2 text-fluid-xs font-normal app-text-muted">
                    {resume.mois.nb_mesures_total} {resume.mois.nb_mesures_total !== 1 ? t("prediction.mesures") : t("prediction.mesure")}
                  </span>
                </h2>
                <div className="grid gap-3 md:grid-cols-2">
                  <BlocTypeJour titre={t("prediction.joursOuvrables")} labelMin={t("prediction.labelMin")} labelMoy={t("prediction.labelMoy")} labelMax={t("prediction.labelMax")} unite={t("prediction.uniteMn")} stats={resume.mois.jours_ouvrables} />
                  <BlocTypeJour titre={t("prediction.weekEnds")} labelMin={t("prediction.labelMin")} labelMoy={t("prediction.labelMoy")} labelMax={t("prediction.labelMax")} unite={t("prediction.uniteMn")} stats={resume.mois.week_ends}
                    messageVide={locale === "fr" ? "Pas encore de week-end ce mois — mis à jour automatiquement à chaque samedi collecté" : "No weekend yet this month — updated automatically each Saturday"} />
                </div>
              </section>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sous-composants
// ---------------------------------------------------------------------------

/** Affiche une durée sur deux lignes : "XX min" (grande) + "YY s" (plus petite) */
function DureeDeuxLignes({
  s,
  classMin,
  classSec,
}: {
  s: number | null;
  classMin: string;
  classSec?: string;
}) {
  if (s == null) return <div className={classMin}>—</div>;
  const mn = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  if (mn === 0) return <div className={classMin}>{sec} s</div>;
  return (
    <>
      <div className={classMin}>{mn} min</div>
      {sec > 0 && <div className={classSec ?? classMin}>{sec} s</div>}
    </>
  );
}

function BlocTypeJour({ titre, stats, labelMin, labelMoy, labelMax, messageVide }: {
  titre: string; stats: import("@/lib/types").StatsPeriode | null;
  labelMin: string; labelMoy: string; labelMax: string; unite?: string;
  messageVide?: string;
}) {
  const toS = (s: number | null | undefined, mn: number | null | undefined): number | null =>
    s != null ? s : mn != null ? Math.round(mn * 60) : null;
  return (
    <div className="paa-card p-3">
      <div className="text-fluid-xs font-semibold text-paa-navy-700 dark:text-paa-blue-100 mb-2">{titre}</div>
      {stats === null ? (
        <p className="text-fluid-xs app-text-muted italic">
          {messageVide ?? "—"}
        </p>
      ) : (
        <div className="grid grid-cols-3 gap-1 text-center">
          <div>
            <div className="text-fluid-xs app-text-muted">{labelMin}</div>
            <DureeDeuxLignes
              s={toS(stats.min_s, stats.min_mn)}
              classMin="font-bold text-fluid-sm text-statut-fluide"
              classSec="text-fluid-xs font-semibold text-statut-fluide"
            />
          </div>
          <div>
            <div className="text-fluid-xs app-text-muted">{labelMoy}</div>
            <DureeDeuxLignes
              s={toS(stats.moyen_s, stats.moyen_mn)}
              classMin="font-bold text-fluid-sm text-paa-blue-500"
              classSec="text-fluid-xs font-semibold text-paa-blue-400"
            />
          </div>
          <div>
            <div className="text-fluid-xs app-text-muted">{labelMax}</div>
            <DureeDeuxLignes
              s={toS(stats.max_s, stats.max_mn)}
              classMin="font-bold text-fluid-sm text-statut-congestionne"
              classSec="text-fluid-xs font-semibold text-statut-congestionne"
            />
          </div>
        </div>
      )}
    </div>
  );
}

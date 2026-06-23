"use client";

/**
 * Résumé des temps de traversée estimés par accumulation de segments GPX.
 *
 * Deux blocs :
 *   1. Explication du principe « précision progressive » (toujours visible).
 *   2. Tableau de synthèse par tronçon : sessions, durée estimée, confiance.
 *
 * Source : GET /terrain/segments/resume (tous les tronçons actifs).
 */

import { useEffect, useState } from "react";

import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { ResumeSegments } from "@/lib/types";

interface ResumeSegmentsProps {
  /** Rechargement déclenché depuis le parent après un import réussi. */
  rafraichir?: number;
}

function formaterMn(s: number | null): string {
  if (s === null) return "—";
  const mn = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return `${mn}:${String(sec).padStart(2, "0")} min`;
}

function BarreConfiance({ confiance }: { confiance: number }) {
  const pct = Math.round(confiance * 100);
  const couleur =
    pct >= 75
      ? "bg-statut-fluide"
      : pct >= 40
        ? "bg-yellow-400"
        : "bg-statut-congestionne";

  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-20 overflow-hidden rounded-full bg-paa-blue-100 dark:bg-paa-navy-700">
        <div className={`h-full ${couleur} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-fluid-xs font-medium tabular-nums">{pct} %</span>
    </div>
  );
}

function BadgeSource({ source }: { source: string }) {
  const isMiroir = source === "miroir_aller_retour";
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-fluid-xs ${
        isMiroir
          ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300"
          : "bg-paa-blue-100 text-paa-navy-700 dark:bg-paa-navy-700 dark:text-paa-blue-100"
      }`}
    >
      {isMiroir ? "miroir" : "direct"}
    </span>
  );
}

export function ResumeSegmentsBlock({ rafraichir = 0 }: ResumeSegmentsProps) {
  const { t } = useI18n();
  const [resumes, setResumes] = useState<ResumeSegments[]>([]);
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState<string | null>(null);
  const [explicationOuverte, setExplicationOuverte] = useState(false);

  useEffect(() => {
    let actif = true;
    setChargement(true);
    api
      .segmentsResume()
      .then((data) => {
        if (actif) {
          setResumes(data);
          setErreur(null);
        }
      })
      .catch((e) => {
        if (actif) setErreur(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (actif) setChargement(false);
      });
    return () => {
      actif = false;
    };
  }, [rafraichir]);

  const totalSessions = resumes.reduce((acc, r) => acc + r.nb_sessions, 0);
  const tronconsAvecDonnees = resumes.filter((r) => r.temps_moyen_s !== null).length;

  return (
    <Card
      titre={t("segments.resumeTitle")}
      description={t("segments.resumeDescription")}
    >
      {/* ------------------------------------------------------------------ */}
      {/* Bloc « Comment ça marche » (accordéon)                              */}
      {/* ------------------------------------------------------------------ */}
      <button
        type="button"
        onClick={() => setExplicationOuverte((v) => !v)}
        className="mb-4 flex w-full items-center justify-between rounded-md border app-border bg-paa-blue-50 dark:bg-paa-navy-800 px-4 py-3 text-left"
      >
        <span className="text-fluid-sm font-semibold text-paa-navy-800 dark:text-paa-blue-100">
          {t("segments.explicationTitle")}
        </span>
        <span className="text-paa-navy-400 dark:text-paa-blue-300">
          {explicationOuverte ? "▲" : "▼"}
        </span>
      </button>

      {explicationOuverte && (
        <div className="mb-5 rounded-md border app-border bg-white dark:bg-paa-navy-900 p-4 flex flex-col gap-4 text-fluid-sm">
          {/* Principe */}
          <section>
            <h4 className="font-semibold text-paa-navy-800 dark:text-paa-blue-100 mb-2">
              {t("segments.principeTitle")}
            </h4>
            <p className="app-text-muted leading-relaxed">
              {t("segments.explication1")}
            </p>
            <p className="app-text-muted leading-relaxed mt-2">
              {t("segments.explication2")}
            </p>
          </section>

          {/* Schéma de confiance */}
          <section>
            <h4 className="font-semibold text-paa-navy-800 dark:text-paa-blue-100 mb-2">
              {t("segments.confianceTitle")}
            </h4>
            <div className="grid gap-2 sm:grid-cols-2 text-fluid-xs">
              {[
                { pct: "0–25 %", label: t("segments.confiance0"), couleur: "bg-statut-congestionne" },
                { pct: "25–50 %", label: t("segments.confiance1"), couleur: "bg-yellow-400" },
                { pct: "50–75 %", label: t("segments.confiance2"), couleur: "bg-yellow-400" },
                { pct: "75–100 %", label: t("segments.confiance3"), couleur: "bg-statut-fluide" },
              ].map(({ pct, label, couleur }) => (
                <div key={pct} className="flex items-center gap-3 rounded border app-border px-3 py-2">
                  <div className={`h-3 w-3 shrink-0 rounded-full ${couleur}`} />
                  <div>
                    <span className="font-semibold">{pct}</span>
                    <span className="app-text-muted"> — {label}</span>
                  </div>
                </div>
              ))}
            </div>
            <p className="app-text-muted mt-2">
              {t("segments.explication3")}
            </p>
          </section>

          {/* Procédure */}
          <section>
            <h4 className="font-semibold text-paa-navy-800 dark:text-paa-blue-100 mb-2">
              {t("segments.procedureTitle")}
            </h4>
            <ol className="list-decimal pl-5 space-y-1 app-text-muted">
              {[
                t("segments.comment1"),
                t("segments.comment2"),
                t("segments.comment3"),
                t("segments.comment4"),
              ].map((etape, i) => (
                <li key={i}>{etape}</li>
              ))}
            </ol>
            <div className="mt-3 rounded-md bg-paa-blue-50 dark:bg-paa-navy-800 border app-border px-3 py-2 text-fluid-xs app-text-muted">
              <strong>{t("segments.noteMiroir")}</strong>{" "}
              {t("segments.noteMiroirDetail")}
            </div>
          </section>
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* KPI résumé                                                          */}
      {/* ------------------------------------------------------------------ */}
      <div className="mb-4 grid gap-2 sm:grid-cols-3 text-fluid-xs">
        <KpiBox label={t("segments.kpiSessions")} valeur={String(totalSessions)} />
        <KpiBox label={t("segments.kpiTroncons")} valeur={`${tronconsAvecDonnees} / ${resumes.length}`} />
        <KpiBox
          label={t("segments.kpiConfianceMoy")}
          valeur={
            resumes.length > 0
              ? `${Math.round((resumes.reduce((a, r) => a + r.confiance, 0) / resumes.length) * 100)} %`
              : "—"
          }
        />
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Tableau principal                                                   */}
      {/* ------------------------------------------------------------------ */}
      {chargement && (
        <p className="text-fluid-xs app-text-muted">{t("common.loading")}</p>
      )}
      {erreur && (
        <p className="text-fluid-xs text-statut-congestionne">{erreur}</p>
      )}
      {!chargement && !erreur && resumes.length === 0 && (
        <p className="text-fluid-xs app-text-muted">{t("segments.aucunSegment")}</p>
      )}

      {!chargement && resumes.length > 0 && (
        <div className="overflow-x-auto">
          <table className="min-w-full text-fluid-xs">
            <thead className="bg-paa-blue-50 dark:bg-paa-navy-800">
              <tr className="text-left">
                <Th>{t("segments.colTroncon")}</Th>
                <Th>{t("segments.colSessions")}</Th>
                <Th>{t("segments.colMoyen")}</Th>
                <Th>{t("segments.colMin")}</Th>
                <Th>{t("segments.colMax")}</Th>
                <Th>{t("segments.colCouverture")}</Th>
                <Th>{t("segments.colConfiance")}</Th>
              </tr>
            </thead>
            <tbody>
              {resumes.map((r) => {
                const sourcePremiere = r.sessions[0]?.source ?? "segments_directs";
                return (
                  <tr key={r.troncon_id} className="border-t app-border">
                    <Td>
                      <div className="font-medium text-paa-navy-800 dark:text-paa-blue-100">
                        {r.troncon_nom}
                      </div>
                      <BadgeSource source={sourcePremiere} />
                    </Td>
                    <Td className="tabular-nums font-medium">
                      {r.nb_sessions > 0 ? r.nb_sessions : "—"}
                    </Td>
                    <Td className="tabular-nums font-semibold text-paa-navy-900 dark:text-paa-blue-100">
                      {formaterMn(r.temps_moyen_s)}
                    </Td>
                    <Td className="tabular-nums text-statut-fluide">
                      {formaterMn(r.temps_min_s)}
                    </Td>
                    <Td className="tabular-nums text-statut-congestionne">
                      {formaterMn(r.temps_max_s)}
                    </Td>
                    <Td className="tabular-nums">
                      {r.couverture_moyenne_pct.toFixed(0)} %
                    </Td>
                    <Td>
                      {r.nb_sessions > 0 ? (
                        <BarreConfiance confiance={r.confiance} />
                      ) : (
                        <span className="app-text-muted text-fluid-xs">
                          {t("segments.aucunSegmentRow")}
                        </span>
                      )}
                    </Td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function KpiBox({ label, valeur }: { label: string; valeur: string }) {
  return (
    <div className="rounded-md border app-border px-3 py-2 app-surface">
      <div className="text-fluid-xs app-text-muted">{label}</div>
      <div className="font-semibold text-paa-navy-900 dark:text-paa-blue-100">{valeur}</div>
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th className="px-2 py-2 font-medium text-paa-navy-700 dark:text-paa-blue-100 whitespace-nowrap">
      {children}
    </th>
  );
}

function Td({ children, className }: { children: React.ReactNode; className?: string }) {
  return <td className={`px-2 py-2 align-middle ${className ?? ""}`}>{children}</td>;
}

"use client";

/**
 * Heatmap horaire — grille jour de semaine × heure de la journée (7 × 24).
 *
 * Chaque case représente la moyenne historique du temps de traversée pour
 * ce créneau, exprimée en ratio par rapport au temps fluide de référence :
 *   - ratio 1,0  → fluide (case verte claire)
 *   - ratio 2,0  → 2× le temps fluide (case orange)
 *   - ratio 3,0+ → 3× le temps fluide (case rouge foncée)
 *
 * Alimentée par /profils/troncons/{id} pour les 7 jours de la semaine.
 * Charge les 7 profils en parallèle.
 */

import { useEffect, useState } from "react";

import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { JourSemaine, ProfilHoraire } from "@/lib/types";

const JOURS_ORDRE: JourSemaine[] = [
  "lundi",
  "mardi",
  "mercredi",
  "jeudi",
  "vendredi",
  "samedi",
  "dimanche",
];

const HEURES = Array.from({ length: 24 }, (_, i) => i);

export function HeatmapHoraire({ tronconId }: { tronconId: number | null }) {
  const { t, locale } = useI18n();
  const [profils, setProfils] = useState<Record<JourSemaine, ProfilHoraire | null>>({
    lundi: null,
    mardi: null,
    mercredi: null,
    jeudi: null,
    vendredi: null,
    samedi: null,
    dimanche: null,
  });
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    if (tronconId === null) return;
    let annule = false;
    setChargement(true);
    setErreur(null);

    Promise.allSettled(
      JOURS_ORDRE.map((j) => api.profilHoraire(tronconId, j, 90)),
    )
      .then((results) => {
        if (annule) return;
        const nouveauProfils = { ...profils };
        results.forEach((r, idx) => {
          const jour = JOURS_ORDRE[idx];
          nouveauProfils[jour] = r.status === "fulfilled" ? r.value : null;
        });
        setProfils(nouveauProfils);
      })
      .catch((e) => !annule && setErreur(String(e)))
      .finally(() => !annule && setChargement(false));

    return () => {
      annule = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tronconId]);

  // Détermine le temps de référence (commun aux 7 jours d'un même tronçon)
  const refS =
    Object.values(profils).find((p) => p !== null)?.troncon.temps_reference_s ??
    null;

  return (
    <Card
      titre={t("indicateurs.heatmapTitle")}
      description={t("indicateurs.heatmapSubtitle")}
    >
      {chargement && (
        <div className="flex h-[260px] items-center justify-center text-fluid-sm app-text-muted">
          {t("common.loading")}
        </div>
      )}
      {erreur && (
        <div className="text-fluid-sm text-statut-congestionne">
          {t("common.error")} : {erreur}
        </div>
      )}
      {!chargement && !erreur && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] border-separate border-spacing-0.5 text-fluid-xs">
              <thead>
                <tr>
                  <th className="sticky left-0 z-10 app-surface px-1 py-1 text-left font-medium app-text-muted">
                    {/* coin vide */}
                  </th>
                  {HEURES.map((h) => (
                    <th
                      key={h}
                      className="px-0 py-1 text-center font-medium app-text-muted"
                    >
                      {h}h
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {JOURS_ORDRE.map((j) => {
                  const profil = profils[j];
                  const points = Array.isArray(profil?.points) ? profil!.points : [];
                  const labelKey = `indicateurs.jour${j.charAt(0).toUpperCase() + j.slice(1)}`;
                  return (
                    <tr key={j}>
                      <th className="sticky left-0 z-10 app-surface px-2 py-1 text-left font-medium app-text-muted">
                        {t(labelKey)}
                      </th>
                      {HEURES.map((h) => {
                        const point = points.find((p) => p.heure === h);
                        const moyS = point?.moyenne_s ?? null;
                        const ratio =
                          moyS !== null && refS && refS > 0 ? moyS / refS : null;
                        return (
                          <td
                            key={h}
                            className="h-7 min-w-[24px] rounded border app-border text-center align-middle font-medium text-[10px]"
                            style={{
                              backgroundColor: couleurRatio(ratio),
                              color: contrasteTexte(ratio),
                            }}
                            title={
                              ratio !== null
                                ? `${t(labelKey)} ${h}h — ${(moyS! / 60).toFixed(1)} min (ratio ${ratio.toFixed(2)})`
                                : `${t(labelKey)} ${h}h — ${t("common.noData")}`
                            }
                          >
                            {ratio !== null ? ratio.toFixed(1) : ""}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Légende de la heatmap */}
          <div className="mt-3 flex flex-wrap items-center gap-2 text-fluid-xs app-text-muted">
            <span>{t("indicateurs.heatmapLegend")}</span>
            <div className="flex items-center gap-1">
              {[1.0, 1.3, 1.7, 2.0, 2.5, 3.0].map((v) => (
                <span
                  key={v}
                  className="inline-block h-4 w-6 rounded text-center text-[10px] font-medium"
                  style={{
                    backgroundColor: couleurRatio(v),
                    color: contrasteTexte(v),
                    lineHeight: "1rem",
                  }}
                >
                  {v.toFixed(1)}
                </span>
              ))}
            </div>
          </div>
        </>
      )}
    </Card>
  );
}

// Couleur pour un ratio donné — gradient vert (1.0) → orange (2.0) → rouge (3.0)
function couleurRatio(ratio: number | null): string {
  if (ratio === null) return "rgba(149, 165, 166, 0.12)"; // gris très clair
  // Clamp 1.0..3.0
  const t = Math.min(1, Math.max(0, (ratio - 1) / 2));
  if (t < 0.5) {
    // 1.0 → 2.0 : vert → orange
    const u = t * 2;
    const r = Math.round(46 + (243 - 46) * u);
    const g = Math.round(204 + (156 - 204) * u);
    const b = Math.round(113 + (18 - 113) * u);
    return `rgb(${r}, ${g}, ${b})`;
  }
  // 2.0 → 3.0 : orange → rouge
  const u = (t - 0.5) * 2;
  const r = Math.round(243 + (231 - 243) * u);
  const g = Math.round(156 + (76 - 156) * u);
  const b = Math.round(18 + (60 - 18) * u);
  return `rgb(${r}, ${g}, ${b})`;
}

// Texte clair sur fond foncé, sombre sur fond clair
function contrasteTexte(ratio: number | null): string {
  if (ratio === null) return "rgba(0,0,0,0.4)";
  return ratio > 1.5 ? "white" : "#0B2545";
}

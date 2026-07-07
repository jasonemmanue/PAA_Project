"use client";

/**
 * Panneau latéral de la page Carte — version DEESP (couleurs Google Maps).
 *
 *   1. **Bandeau KPI** — compteurs par classe DEESP :
 *        • Fluide (vert)
 *        • Congestionné (rouge)
 *        • Indéterminé (gris) — Google n'a pas qualifié le tracé
 *
 *   2. **Point chaud** — encart mettant en valeur le tronçon
 *      le plus dégradé du moment. Critère : « congestionné » selon la
 *      couleur Google Maps (rouge ou orange long).
 *
 *   3. **Liste des tronçons surveillés** — triée du plus dégradé au plus fluide,
 *      chaque ligne cliquable déclenche un recentrage animé de la carte.
 *      Affiche pour chaque tronçon les pourcentages de rouge / orange / vert
 *      (lecture directe des couleurs Google Maps).
 */

import clsx from "clsx";

import {
  couleurClasseCongestion,
  formaterDuree,
  formaterHeureAbidjan,
  libelleClasseCongestion,
  libelleSource,
} from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { CarteEtat, ClasseCongestion } from "@/lib/types";

const ORDRE_GRAVITE: Record<ClasseCongestion, number> = {
  congestionne: 2,
  fluide: 1,
  indetermine: 0,
};

type Props = {
  etat: CarteEtat | null;
  selectionId: number | null;
  selectionSousId?: number | null;
  onSelectionner: (id: number) => void;
  onSelectionnerSous?: (sousId: number, parentId: number) => void;
};

export function PanneauTroncons({
  etat,
  selectionId,
  selectionSousId = null,
  onSelectionner,
  onSelectionnerSous,
}: Props) {
  const { t, locale } = useI18n();

  if (!etat) {
    return (
      <div className="paa-card p-4 text-fluid-sm app-text-muted">
        {t("common.loading")}
      </div>
    );
  }

  // Un axe = entrée dans `troncons` (les 6 axes DEESP principaux).
  // Un tronçon = sous_tronçon codifié enfant d'un axe (table `sous_troncons`).
  // On ignore volontairement les entrées est_axe=false — orphelins archivés
  // dans le cadre du refactor 2026-07-04 (migration vers sous_troncons).
  const troncsAxes = etat.troncons.filter((tr) => tr.est_axe !== false);
  const nbAxes = troncsAxes.length;
  const nbTroncons = troncsAxes.reduce(
    (n, tr) => n + (tr.sous_troncons?.length ?? 0),
    0,
  );

  // KPI counts (3 classes DEESP) — un axe avec sous-tronçons est remplacé
  // par la granularité fine (cf. règle scheduler § 4.8 : on ne mesure pas
  // l'axe parent quand il a des sous-tronçons actifs).
  const compteurs: Record<ClasseCongestion, number> = {
    fluide: 0,
    congestionne: 0,
    indetermine: 0,
  };
  for (const tr of troncsAxes) {
    const sous = tr.sous_troncons ?? [];
    if (sous.length > 0) {
      for (const s of sous) compteurs[s.classe_congestion]++;
    } else {
      compteurs[tr.classe_congestion]++;
    }
  }

  const composerLibelle = (locale: "fr" | "en"): string => {
    const partAxes =
      locale === "fr"
        ? `${nbAxes} axe${nbAxes > 1 ? "s" : ""}`
        : `${nbAxes} ax${nbAxes > 1 ? "es" : "is"}`;
    const partTroncons =
      locale === "fr"
        ? `${nbTroncons} tronçon${nbTroncons > 1 ? "s" : ""}`
        : `${nbTroncons} segment${nbTroncons > 1 ? "s" : ""}`;
    if (nbTroncons === 0) return partAxes;
    if (nbAxes === 0) return partTroncons;
    return locale === "fr"
      ? `${partAxes} et ${partTroncons}`
      : `${partAxes} and ${partTroncons}`;
  };

  // Tri par gravité décroissante : congestionnés (worst rouge%) en tête.
  // On n'affiche que les axes — les orphelins est_axe=false n'ont plus vocation
  // à figurer dans la liste (soit sous-tronçons, soit à archiver).
  const tronconsTries = troncsAxes.slice().sort((a, b) => {
    const ga = ORDRE_GRAVITE[a.classe_congestion];
    const gb = ORDRE_GRAVITE[b.classe_congestion];
    if (ga !== gb) return gb - ga;
    const ra = a.couleur_google?.pourcentage_rouge ?? 0;
    const rb = b.couleur_google?.pourcentage_rouge ?? 0;
    if (ra !== rb) return rb - ra;
    const oa = a.couleur_google?.pourcentage_orange ?? 0;
    const ob = b.couleur_google?.pourcentage_orange ?? 0;
    return ob - oa;
  });
  const pointChaud = tronconsTries.find(
    (tr) => tr.classe_congestion === "congestionne",
  );

  return (
    <div className="flex flex-col gap-fluid-4">
      {/* ── Bandeau KPI ── */}
      <div className="paa-card p-3">
        <p className="mb-2 text-fluid-xs font-medium app-text-muted">
          {locale === "fr"
            ? `État : ${composerLibelle("fr")} (couleurs Google Maps)`
            : `Status: ${composerLibelle("en")} (Google Maps colours)`}
        </p>
        <div className="grid grid-cols-3 gap-2">
          <KpiCompteur
            valeur={compteurs.fluide}
            libelle={libelleClasseCongestion("fluide", locale)}
            couleur="#16a34a"
          />
          <KpiCompteur
            valeur={compteurs.congestionne}
            libelle={libelleClasseCongestion("congestionne", locale)}
            couleur="#E74C3C"
          />
          <KpiCompteur
            valeur={compteurs.indetermine}
            libelle={libelleClasseCongestion("indetermine", locale)}
            couleur="#95A5A6"
          />
        </div>
      </div>

      {/* ── Point chaud — affiché uniquement s'il y en a un ── */}
      {pointChaud && (
        <button
          type="button"
          onClick={() => onSelectionner(pointChaud.id)}
          className="paa-card flex items-start gap-3 p-3 text-left transition-colors hover:bg-paa-blue-50 dark:hover:bg-paa-navy-700"
          style={{
            borderLeft: `4px solid ${couleurClasseCongestion(pointChaud.classe_congestion)}`,
          }}
        >
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
               style={{
                 backgroundColor: `${couleurClasseCongestion(pointChaud.classe_congestion)}22`,
               }}>
            <span className="text-lg" aria-hidden>⚠</span>
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-fluid-xs font-medium uppercase tracking-wide"
               style={{ color: couleurClasseCongestion(pointChaud.classe_congestion) }}>
              {locale === "fr" ? "Point chaud actuel" : "Current hotspot"}
            </p>
            <p className="text-fluid-sm font-semibold text-paa-navy-900 dark:text-paa-blue-100 truncate">
              {pointChaud.nom}
            </p>
            <p className="text-fluid-xs app-text-muted">
              {pointChaud.couleur_google?.pourcentage_rouge !== null &&
                pointChaud.couleur_google?.pourcentage_rouge !== undefined &&
                `🔴 ${pointChaud.couleur_google.pourcentage_rouge.toFixed(1)}% `}
              {pointChaud.couleur_google?.pourcentage_orange !== null &&
                pointChaud.couleur_google?.pourcentage_orange !== undefined &&
                `· 🟠 ${pointChaud.couleur_google.pourcentage_orange.toFixed(1)}% `}
              {pointChaud.derniere_mesure?.duree_trafic_s &&
                `· ${formaterDuree(pointChaud.derniere_mesure.duree_trafic_s)}`}
            </p>
          </div>
        </button>
      )}

      {/* ── Liste triée des tronçons ── */}
      <div className="paa-card overflow-hidden">
        <div className="border-b app-border bg-paa-blue-100 px-4 py-2 text-fluid-sm font-semibold
                        text-paa-navy-900 dark:bg-paa-navy-700 dark:text-paa-blue-100">
          {locale === "fr"
            ? `${composerLibelle("fr")} surveillés`
            : `${composerLibelle("en")} monitored`}
        </div>
        <ul className="divide-y divide-[rgb(var(--app-border))]">
          {tronconsTries.map((tr) => {
            const couleur = couleurClasseCongestion(tr.classe_congestion);
            const dureeTrafic = formaterDuree(tr.derniere_mesure?.duree_trafic_s);
            const actif = selectionId === tr.id;
            const pctR = tr.couleur_google?.pourcentage_rouge;
            const pctO = tr.couleur_google?.pourcentage_orange;
            const pctV = tr.couleur_google?.pourcentage_vert;
            const horoMesure = tr.derniere_mesure?.horodatage_local
              ?? tr.derniere_mesure?.horodatage_utc
              ?? tr.derniere_mesure?.horodatage;

            return (
              <li key={tr.id}>
                <button
                  type="button"
                  onClick={() => onSelectionner(tr.id)}
                  aria-pressed={actif}
                  className={clsx(
                    "flex w-full items-start gap-3 px-4 py-3 text-left transition-colors",
                    actif
                      ? "bg-paa-blue-50 dark:bg-paa-navy-700"
                      : "hover:bg-paa-blue-50 dark:hover:bg-paa-navy-800",
                  )}
                  style={actif ? { borderLeft: `4px solid ${couleur}` } : undefined}
                >
                  <span
                    className="mt-1 inline-block h-3 w-3 shrink-0 rounded-full"
                    style={{ backgroundColor: couleur }}
                    aria-hidden
                  />
                  <div className="min-w-0 flex-1">
                    <div className="text-fluid-sm font-medium text-paa-navy-900 dark:text-paa-blue-100 truncate">
                      {tr.nom}
                    </div>
                    <div className="mt-0.5 flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-fluid-xs app-text-muted">
                      <span className="font-semibold" style={{ color: couleur }}>
                        {tr.libelle_classe ?? libelleClasseCongestion(tr.classe_congestion, locale)}
                      </span>
                      <span>
                        {locale === "fr" ? "Temps actuel " : "Current "}
                        <span className="font-semibold text-paa-navy-900 dark:text-paa-blue-100">
                          {dureeTrafic}
                        </span>
                      </span>
                    </div>
                    {/* Barre couleur Google Maps : rouge / orange / vert */}
                    {(pctR !== null && pctR !== undefined) ||
                    (pctO !== null && pctO !== undefined) ? (
                      <>
                        <div className="mt-1.5 flex h-1.5 w-full overflow-hidden rounded-full bg-gray-200">
                          <div
                            style={{ width: `${pctR ?? 0}%`, backgroundColor: "#E74C3C" }}
                          />
                          <div
                            style={{ width: `${pctO ?? 0}%`, backgroundColor: "#F39C12" }}
                          />
                          <div
                            style={{ width: `${pctV ?? 0}%`, backgroundColor: "#16a34a" }}
                          />
                        </div>
                        <div className="mt-1 flex gap-2 text-fluid-xs app-text-muted">
                          {pctR !== null && pctR !== undefined && (
                            <span style={{ color: "#E74C3C" }}>🔴 {pctR.toFixed(1)}%</span>
                          )}
                          {pctO !== null && pctO !== undefined && (
                            <span style={{ color: "#F39C12" }}>🟠 {pctO.toFixed(1)}%</span>
                          )}
                          {pctV !== null && pctV !== undefined && (
                            <span style={{ color: "#16a34a" }}>🟢 {pctV.toFixed(1)}%</span>
                          )}
                        </div>
                      </>
                    ) : null}
                    <div className="mt-1 text-fluid-xs app-text-muted truncate">
                      {libelleSource(tr.derniere_mesure?.source)} ·{" "}
                      {formaterHeureAbidjan(horoMesure)}
                    </div>
                  </div>
                </button>

                {/* Sous-tronçons codifiés (T1A, T2A…) — cliquables pour zoomer
                    sur leur portion précise de l'axe parent. */}
                {(tr.sous_troncons ?? []).length > 0 && (
                  <ul className="ml-6 border-l-2 border-paa-blue-100 dark:border-paa-navy-700">
                    {(tr.sous_troncons ?? []).map((sous) => {
                      const couleurSous = couleurClasseCongestion(
                        sous.classe_congestion,
                      );
                      const actifSous = selectionSousId === sous.id;
                      const dureeSous = formaterDuree(
                        sous.derniere_mesure?.duree_trafic_s,
                      );
                      return (
                        <li key={`sous-${sous.id}`}>
                          <button
                            type="button"
                            onClick={() =>
                              onSelectionnerSous?.(sous.id, tr.id)
                            }
                            aria-pressed={actifSous}
                            className={clsx(
                              "flex w-full items-center gap-3 px-4 py-2 text-left text-fluid-xs transition-colors",
                              actifSous
                                ? "bg-paa-blue-50 dark:bg-paa-navy-700"
                                : "hover:bg-paa-blue-50 dark:hover:bg-paa-navy-800",
                            )}
                            style={
                              actifSous
                                ? { borderLeft: `3px solid ${couleurSous}` }
                                : undefined
                            }
                          >
                            {sous.sens_symbole && (
                              <span className="shrink-0 text-base text-paa-navy-600 dark:text-paa-blue-300">
                                {sous.sens_symbole}
                              </span>
                            )}
                            <span
                              className="inline-flex h-6 min-w-[2rem] shrink-0 items-center justify-center rounded px-1.5 text-[0.65rem] font-bold text-white"
                              style={{ backgroundColor: couleurSous }}
                            >
                              {sous.code}
                            </span>
                            <span className="min-w-0 flex-1 truncate text-paa-navy-900 dark:text-paa-blue-100">
                              {sous.nom_court}
                            </span>
                            {sous.distance_km !== undefined && (
                              <span className="shrink-0 app-text-muted">
                                {sous.distance_km.toFixed(2)} km
                              </span>
                            )}
                            {sous.derniere_mesure?.duree_trafic_s != null && (
                              <span
                                className="shrink-0 font-semibold"
                                style={{ color: couleurSous }}
                              >
                                {dureeSous}
                              </span>
                            )}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}

function KpiCompteur({
  valeur,
  libelle,
  couleur,
}: {
  valeur: number;
  libelle: string;
  couleur: string;
}) {
  return (
    <div
      className="rounded-md border app-border bg-white px-2 py-2 text-center dark:bg-paa-navy-800"
      style={{ borderTopColor: couleur, borderTopWidth: 3 }}
    >
      <div className="text-fluid-2xl font-bold leading-none" style={{ color: couleur }}>
        {valeur}
      </div>
      <div className="mt-1 text-fluid-xs app-text-muted truncate">{libelle}</div>
    </div>
  );
}

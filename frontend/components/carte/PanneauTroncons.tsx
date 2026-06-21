"use client";

/**
 * Panneau latéral de la page Carte. Trois zones :
 *
 *   1. **Bandeau KPI** — compteurs par classe (fluide / dense / congestionné)
 *      + nombre total surveillé. Donne l'état d'ensemble en un coup d'œil.
 *
 *   2. **Point chaud** — encart mettant en valeur le tronçon le plus dégradé
 *      du moment (worst classe, puis worst TTI). Permet à l'opérateur PAA de
 *      voir immédiatement où la situation appelle attention.
 *
 *   3. **Liste des tronçons surveillés** — triée du plus dégradé au plus fluide, chaque
 *      ligne cliquable déclenche un recentrage animé de la carte. Le tronçon
 *      sélectionné est marqué d'un bord coloré et d'un fond contrasté.
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
  congestionne: 3,
  dense: 2,
  fluide: 1,
  indetermine: 0,
};

type Props = {
  etat: CarteEtat | null;
  selectionId: number | null;
  onSelectionner: (id: number) => void;
};

export function PanneauTroncons({ etat, selectionId, onSelectionner }: Props) {
  const { t, locale } = useI18n();

  if (!etat) {
    return (
      <div className="paa-card p-4 text-fluid-sm app-text-muted">
        {t("common.loading")}
      </div>
    );
  }

  // KPI counts
  const compteurs: Record<ClasseCongestion, number> = {
    fluide: 0, dense: 0, congestionne: 0, indetermine: 0,
  };
  for (const tr of etat.troncons) compteurs[tr.classe_congestion]++;

  // Tri par gravité décroissante pour la liste + détection du point chaud
  const tronconsTries = etat.troncons.slice().sort((a, b) => {
    const ga = ORDRE_GRAVITE[a.classe_congestion];
    const gb = ORDRE_GRAVITE[b.classe_congestion];
    if (ga !== gb) return gb - ga;
    return (b.tti ?? 0) - (a.tti ?? 0);
  });
  const pointChaud = tronconsTries.find(
    (tr) => tr.classe_congestion === "congestionne" || tr.classe_congestion === "dense",
  );

  return (
    <div className="flex flex-col gap-fluid-4">
      {/* ── Bandeau KPI ── */}
      <div className="paa-card p-3">
        <p className="mb-2 text-fluid-xs font-medium app-text-muted">
          {locale === "fr"
            ? `État des ${etat.nb_troncons} tronçons`
            : `Status of the ${etat.nb_troncons} segments`}
        </p>
        <div className="grid grid-cols-3 gap-2">
          <KpiCompteur
            valeur={compteurs.fluide}
            libelle={libelleClasseCongestion("fluide", locale)}
            couleur="#2ECC71"
          />
          <KpiCompteur
            valeur={compteurs.dense}
            libelle={libelleClasseCongestion("dense", locale)}
            couleur="#F39C12"
          />
          <KpiCompteur
            valeur={compteurs.congestionne}
            libelle={libelleClasseCongestion("congestionne", locale)}
            couleur="#E74C3C"
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
              {libelleClasseCongestion(pointChaud.classe_congestion, locale)}
              {pointChaud.tti !== null && ` · TTI ${pointChaud.tti.toFixed(2)}`}
              {pointChaud.derniere_mesure?.duree_trafic_s &&
                ` · ${formaterDuree(pointChaud.derniere_mesure.duree_trafic_s)}`}
            </p>
          </div>
        </button>
      )}

      {/* ── Liste triée des tronçons ── */}
      <div className="paa-card overflow-hidden">
        <div className="border-b app-border bg-paa-blue-100 px-4 py-2 text-fluid-sm font-semibold
                        text-paa-navy-900 dark:bg-paa-navy-700 dark:text-paa-blue-100">
          {locale === "fr"
            ? `${etat.nb_troncons} tronçons surveillés`
            : `${etat.nb_troncons} segments monitored`}
        </div>
        <ul className="divide-y divide-[rgb(var(--app-border))]">
          {tronconsTries.map((tr) => {
            const couleur = couleurClasseCongestion(tr.classe_congestion);
            const dureeTrafic = formaterDuree(tr.derniere_mesure?.duree_trafic_s);
            const actif = selectionId === tr.id;

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
                        {libelleClasseCongestion(tr.classe_congestion, locale)}
                      </span>
                      <span>
                        {locale === "fr" ? "Temps actuel " : "Current "}
                        <span className="font-semibold text-paa-navy-900 dark:text-paa-blue-100">
                          {dureeTrafic}
                        </span>
                      </span>
                      <span>
                        {tr.tti !== null
                          ? `ITP ${tr.tti.toFixed(2)}`
                          : "ITP —"}
                      </span>
                    </div>
                    <div className="mt-1 text-fluid-xs app-text-muted truncate">
                      {libelleSource(tr.derniere_mesure?.source)} ·{" "}
                      {formaterHeureAbidjan(tr.derniere_mesure?.horodatage)}
                    </div>
                  </div>
                </button>
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

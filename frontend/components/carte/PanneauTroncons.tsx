"use client";

/**
 * Panneau latéral de la page Accueil / Carte — vue centrée sur les axes.
 *
 *   1. **État des axes** — compteurs Fluide / Congestionné / Indéterminé
 *      calculés sur la classe d'axe (`classe_axe`) : un axe est congestionné
 *      quand au moins 50 % de sa distance est en tronçons congestionnés
 *      (couleurs Google Maps, règle DEESP au niveau tronçon).
 *
 *   2. **Axes chauds** — axes congestionnés, du plus touché au moins touché
 *      (part de distance congestionnée, puis dépassement du temps de
 *      référence). Remplace l'ancien « point chaud » de tronçon.
 *
 *   3. **Temps de traversée des axes** — tableau compact : temps actuel
 *      (mesure Google du créneau) + min / moyen / max sur les 7 derniers
 *      jours du même type de jour, comme la page Temps de traversée.
 *
 *   4. **Liste des axes** — un cadre par axe (sens, classe, temps total)
 *      contenant ses tronçons codifiés cliquables pour un zoom fin.
 */

import clsx from "clsx";

import {
  ACCUEIL_AXES_SEULS,
  couleurClasseCongestion,
  formaterDuree,
  formaterDureeCompacte,
  formaterHeureAbidjan,
  libelleClasseCongestion,
  libelleSource,
} from "@/lib/format";
import { BadgeSensAxe, nomCourtAxe } from "@/components/carte/SensAxe";
import { useI18n } from "@/lib/i18n";
import type {
  CarteEtat,
  ClasseCongestion,
  EtatTronconCarte,
  ResumeAxe,
  ResumeAxes,
} from "@/lib/types";

type Props = {
  etat: CarteEtat | null;
  resumeAxes: ResumeAxes | null;
  selectionId: number | null;
  selectionSousId?: number | null;
  onSelectionner: (id: number) => void;
  onSelectionnerSous?: (sousId: number, parentId: number) => void;
};

export function PanneauTroncons({
  etat,
  resumeAxes,
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

  const axes = etat.troncons
    .filter((tr) => tr.est_axe !== false)
    .slice()
    .sort((a, b) => a.id - b.id);

  const classeAxe = (tr: EtatTronconCarte): ClasseCongestion =>
    tr.classe_axe ?? tr.classe_congestion ?? "indetermine";

  const compteurs: Record<ClasseCongestion, number> = {
    fluide: 0,
    congestionne: 0,
    indetermine: 0,
  };
  for (const tr of axes) compteurs[classeAxe(tr)]++;

  const resumeParAxe = new Map<number, ResumeAxe>(
    (resumeAxes?.axes ?? []).map((r) => [r.troncon_id, r]),
  );
  const ratioReference = (tr: EtatTronconCarte): number | null => {
    const r = resumeParAxe.get(tr.id);
    if (!r?.temps_actuel_s || !r.temps_reference_50kmh_s) return null;
    return r.temps_actuel_s / r.temps_reference_50kmh_s;
  };

  const axesChauds = axes
    .filter((tr) => classeAxe(tr) === "congestionne")
    .sort(
      (a, b) =>
        (b.pct_distance_congestionnee ?? 0) - (a.pct_distance_congestionnee ?? 0)
        || (ratioReference(b) ?? 0) - (ratioReference(a) ?? 0),
    );

  const typeJourLibelle =
    resumeAxes?.type_jour === "week_end"
      ? t("carte.axes.weekEnds")
      : t("carte.axes.joursOuvrables");

  return (
    <div className="flex flex-col gap-fluid-4 pb-56 lg:pb-4">
      {/* ── 1. État des axes ── */}
      <div className="paa-card p-3">
        <p className="mb-2 text-fluid-xs font-medium app-text-muted">
          {t("carte.axes.etat")} : {axes.length}{" "}
          {axes.length > 1 ? t("carte.axes.axes") : t("carte.axes.axe")}
          <span className="ml-1 text-[10px]">({t("carte.axes.regle")})</span>
        </p>
        <div className="grid grid-cols-3 gap-2">
          {(["fluide", "congestionne", "indetermine"] as const).map((c) => (
            <KpiCompteur
              key={c}
              valeur={compteurs[c]}
              libelle={libelleClasseCongestion(c, locale)}
              couleur={couleurClasseCongestion(c)}
            />
          ))}
        </div>
      </div>

      {/* ── 2. Axes chauds ── */}
      <div className="paa-card p-3">
        <p className="mb-2 flex items-center gap-1.5 text-fluid-xs font-semibold uppercase tracking-wide text-statut-congestionne">
          <span aria-hidden>⚠</span> {t("carte.axes.chauds")}
        </p>
        {axesChauds.length === 0 ? (
          <p className="text-fluid-xs app-text-muted">{t("carte.axes.aucunChaud")}</p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {axesChauds.map((tr) => {
              const ratio = ratioReference(tr);
              return (
                <li key={tr.id}>
                  <button
                    type="button"
                    onClick={() => onSelectionner(tr.id)}
                    className={clsx(
                      "flex w-full items-center gap-2 rounded-md border px-2.5 py-2 text-left transition-colors",
                      selectionId === tr.id
                        ? "border-statut-congestionne bg-statut-congestionne/10"
                        : "border-statut-congestionne/30 hover:bg-statut-congestionne/5",
                    )}
                  >
                    <BadgeSensAxe sens={tr.sens_axe} />
                    <span className="min-w-0 flex-1 truncate text-fluid-xs font-semibold text-paa-navy-900 dark:text-paa-blue-50">
                      {nomCourtAxe(tr)}
                    </span>
                    <span className="shrink-0 text-right text-[0.65rem] leading-tight">
                      {tr.pct_distance_congestionnee != null && (
                        <span className="block font-bold text-statut-congestionne">
                          {tr.pct_distance_congestionnee.toFixed(0)} % {t("carte.axes.distance")}
                        </span>
                      )}
                      {ratio !== null && (
                        <span className="block app-text-muted">
                          ×{ratio.toFixed(1)} {t("carte.axes.vsReference")}
                        </span>
                      )}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* ── 3. Temps de traversée des axes ── */}
      <div className="paa-card p-3">
        <p className="mb-1 text-fluid-xs font-semibold uppercase tracking-wide text-paa-navy-600 dark:text-paa-blue-300">
          {t("carte.axes.tempsTitre")}
        </p>
        <p className="mb-2 text-[10px] app-text-muted">
          {t("carte.axes.tempsNote")} {typeJourLibelle}.
          {resumeAxes?.hors_plage_collecte && (
            <span className="ml-1 font-semibold text-amber-600 dark:text-amber-400">
              {t("carte.axes.horsPlage")} ({resumeAxes.plage_collecte}).
            </span>
          )}
        </p>
        {resumeAxes === null ? (
          <p className="text-fluid-xs app-text-muted">{t("common.loading")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[11px] tabular-nums">
              <thead>
                <tr className="border-b app-border text-left app-text-muted">
                  <th className="py-1 pr-1 font-medium">{t("carte.axes.colAxe")}</th>
                  <th className="px-1 py-1 text-right font-medium">{t("carte.axes.colActuel")}</th>
                  <th className="px-1 py-1 text-right font-medium">{t("carte.axes.colMin")}</th>
                  <th className="px-1 py-1 text-right font-medium">{t("carte.axes.colMoy")}</th>
                  <th className="py-1 pl-1 text-right font-medium">{t("carte.axes.colMax")}</th>
                </tr>
              </thead>
              <tbody>
                {axes.map((tr) => {
                  const r = resumeParAxe.get(tr.id);
                  return (
                    <tr
                      key={tr.id}
                      onClick={() => onSelectionner(tr.id)}
                      className={clsx(
                        "cursor-pointer border-b app-border last:border-b-0 transition-colors",
                        selectionId === tr.id
                          ? "bg-paa-blue-50 dark:bg-paa-navy-700"
                          : "hover:bg-paa-blue-50/60 dark:hover:bg-paa-navy-800",
                      )}
                    >
                      <td className="py-1.5 pr-1">
                        <div className="flex items-center gap-1">
                          <span
                            className="inline-block h-2 w-2 shrink-0 rounded-full"
                            style={{ backgroundColor: couleurClasseCongestion(classeAxe(tr)) }}
                            aria-hidden
                          />
                          <span className="font-medium leading-tight text-paa-navy-900 dark:text-paa-blue-50">
                            {nomCourtAxe(tr)}
                          </span>
                        </div>
                      </td>
                      <td className="px-1 py-1.5 text-right font-bold text-paa-navy-900 dark:text-paa-blue-50">
                        {formaterDureeCompacte(r?.temps_actuel_s)}
                      </td>
                      <td className="px-1 py-1.5 text-right text-statut-fluide">
                        {formaterDureeCompacte(r?.min_s)}
                      </td>
                      <td className="px-1 py-1.5 text-right text-paa-blue-500">
                        {formaterDureeCompacte(r?.moyen_s)}
                      </td>
                      <td className="py-1.5 pl-1 text-right text-statut-congestionne">
                        {formaterDureeCompacte(r?.max_s)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── 4. Liste des axes — chaque axe dans son propre cadre ── */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2 px-1">
          <span className="text-fluid-xs font-semibold uppercase tracking-wider text-paa-navy-600 dark:text-paa-blue-300">
            {t("carte.axes.surveilles")}
          </span>
          <span className="flex-1 border-t border-slate-200 dark:border-paa-navy-600" />
        </div>

        <ul className="flex flex-col gap-2">
          {axes.map((tr) => {
            const aSousTroncons = (tr.sous_troncons ?? []).length > 0;
            const classe = classeAxe(tr);
            const couleur = couleurClasseCongestion(classe);
            const dureeTrafic = formaterDuree(tr.derniere_mesure?.duree_trafic_s);
            const actif = selectionId === tr.id;
            const pctR = tr.couleur_google?.pourcentage_rouge;
            const pctO = tr.couleur_google?.pourcentage_orange;
            const pctV = tr.couleur_google?.pourcentage_vert;
            const horoMesure =
              tr.derniere_mesure?.horodatage_local ??
              tr.derniere_mesure?.horodatage_utc ??
              tr.derniere_mesure?.horodatage;

            return (
              <li key={tr.id}>
                <div
                  className={clsx(
                    "overflow-hidden rounded-xl border transition-all duration-200",
                    actif
                      ? "border-paa-blue-400 shadow-lg ring-2 ring-paa-blue-200/60 dark:border-paa-blue-500 dark:ring-paa-blue-700/40"
                      : "border-slate-200 shadow-sm hover:border-paa-blue-200 hover:shadow-md dark:border-paa-navy-600 dark:hover:border-paa-blue-700",
                  )}
                  style={{ borderLeftWidth: 4, borderLeftStyle: "solid", borderLeftColor: couleur }}
                >
                  {/* En-tête axe — cliquable */}
                  <button
                    type="button"
                    onClick={() => onSelectionner(tr.id)}
                    aria-pressed={actif}
                    className={clsx(
                      "flex w-full flex-col px-4 py-3 text-left transition-colors",
                      actif
                        ? "bg-gradient-to-r from-paa-blue-50 to-white dark:from-paa-navy-700 dark:to-paa-navy-800"
                        : "bg-white hover:bg-paa-blue-50/40 dark:bg-paa-navy-800 dark:hover:bg-paa-navy-750",
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className="inline-block h-3.5 w-3.5 shrink-0 rounded-full shadow-sm ring-2 ring-white dark:ring-paa-navy-900"
                        style={{ backgroundColor: couleur }}
                        aria-hidden
                      />
                      <div className="min-w-0 flex-1 truncate text-fluid-sm font-bold text-paa-navy-900 dark:text-paa-blue-50">
                        {tr.nom}
                      </div>
                      <BadgeSensAxe sens={tr.sens_axe} />
                    </div>

                    <div className="ml-6 mt-1.5 flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-fluid-xs app-text-muted">
                      <span className="font-bold" style={{ color: couleur }}>
                        {libelleClasseCongestion(classe, locale)}
                      </span>
                      {aSousTroncons && tr.pct_distance_congestionnee != null && (
                        <span>
                          {tr.pct_distance_congestionnee.toFixed(0)} % {t("carte.axes.distanceCongestionnee")}
                        </span>
                      )}
                      <span>
                        {aSousTroncons ? t("carte.axes.tempsTotal") : t("carte.axes.tempsActuel")}{" "}
                        <span className="font-extrabold text-paa-navy-900 dark:text-paa-blue-100">
                          {dureeTrafic}
                        </span>
                      </span>
                    </div>

                    {!aSousTroncons && (
                      <div className="ml-6">
                        {(pctR != null || pctO != null) && (
                          <>
                            <div className="mt-2 flex h-2 w-full overflow-hidden rounded-full bg-gray-200 shadow-inner dark:bg-slate-700">
                              <div style={{ width: `${pctR ?? 0}%`, backgroundColor: "#E74C3C" }} />
                              <div style={{ width: `${pctO ?? 0}%`, backgroundColor: "#F39C12" }} />
                              <div style={{ width: `${pctV ?? 0}%`, backgroundColor: "#16a34a" }} />
                            </div>
                            <div className="mt-1 flex gap-2 text-fluid-xs app-text-muted">
                              {pctR != null && <span style={{ color: "#E74C3C" }}>🔴 {pctR.toFixed(1)}%</span>}
                              {pctO != null && <span style={{ color: "#F39C12" }}>🟠 {pctO.toFixed(1)}%</span>}
                              {pctV != null && <span style={{ color: "#16a34a" }}>🟢 {pctV.toFixed(1)}%</span>}
                            </div>
                          </>
                        )}
                        <div className="mt-1 truncate text-fluid-xs app-text-muted">
                          {libelleSource(tr.derniere_mesure?.source)} · {formaterHeureAbidjan(horoMesure)}
                        </div>
                      </div>
                    )}
                  </button>

                  {/* Tronçons codifiés — dans le même cadre (masqués en mode axes seuls) */}
                  {aSousTroncons && !ACCUEIL_AXES_SEULS && (
                    <ul className="border-t border-slate-100 bg-slate-50/60 dark:border-paa-navy-700 dark:bg-paa-navy-900/30">
                      {(tr.sous_troncons ?? []).map((sous) => {
                        const couleurSous = couleurClasseCongestion(sous.classe_congestion);
                        const actifSous = selectionSousId === sous.id && selectionId === tr.id;
                        return (
                          <li
                            key={`sous-${sous.id}`}
                            className="border-b border-slate-100 last:border-b-0 dark:border-paa-navy-700/60"
                          >
                            <button
                              type="button"
                              onClick={() => onSelectionnerSous?.(sous.id, tr.id)}
                              aria-pressed={actifSous}
                              className={clsx(
                                "flex w-full items-center gap-2.5 px-4 py-2.5 text-left text-fluid-xs transition-colors",
                                actifSous
                                  ? "bg-paa-blue-50 dark:bg-paa-navy-700"
                                  : "hover:bg-paa-blue-50/70 dark:hover:bg-paa-navy-800",
                              )}
                              style={actifSous ? { borderLeft: `3px solid ${couleurSous}` } : undefined}
                            >
                              {sous.sens_symbole && (
                                <span className="shrink-0 text-sm text-paa-navy-400 dark:text-paa-blue-400">
                                  {sous.sens_symbole}
                                </span>
                              )}
                              <span
                                className="inline-flex h-6 min-w-[2.5rem] shrink-0 items-center justify-center rounded px-1.5 text-[0.65rem] font-bold text-white"
                                style={{ backgroundColor: couleurSous }}
                              >
                                {sous.code}
                              </span>
                              <span className="min-w-0 flex-1 truncate text-paa-navy-800 dark:text-paa-blue-100">
                                {sous.nom_court}
                              </span>
                              {sous.distance_km !== undefined && (
                                <span className="shrink-0 text-[0.65rem] app-text-muted">
                                  {sous.distance_km.toFixed(2)} km
                                </span>
                              )}
                              {sous.derniere_mesure?.duree_trafic_s != null && (
                                <span className="shrink-0 text-[0.7rem] font-semibold" style={{ color: couleurSous }}>
                                  {formaterDuree(sous.derniere_mesure.duree_trafic_s)}
                                </span>
                              )}
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
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

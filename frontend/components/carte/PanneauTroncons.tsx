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
 *   3. **Liste des tronçons surveillés** — chaque axe dans son propre cadre
 *      (card arrondie) contenant à la fois l'en-tête axe cliquable et la
 *      liste de ses sous-tronçons codifiés, aussi cliquables pour un zoom fin.
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

  const troncsAxes = etat.troncons.filter((tr) => tr.est_axe !== false);
  const nbAxes = troncsAxes.length;
  const nbTroncons = troncsAxes.reduce(
    (n, tr) => n + (tr.sous_troncons?.length ?? 0),
    0,
  );

  const compteurs: Record<ClasseCongestion, number> = {
    fluide: 0,
    congestionne: 0,
    indetermine: 0,
  };
  for (const tr of troncsAxes) {
    const sous = tr.sous_troncons ?? [];
    if (sous.length > 0) {
      for (const s of sous) compteurs[s.classe_congestion]++;
    } else if (tr.classe_congestion) {
      compteurs[tr.classe_congestion]++;
    }
  }

  const composerLibelle = (locale: "fr" | "en"): string => {
    const n = nbTroncons > 0 ? nbTroncons : nbAxes;
    if (locale === "fr") {
      const unite = nbTroncons > 0 ? `tronçon${n > 1 ? "s" : ""}` : `axe${n > 1 ? "s" : ""}`;
      return `${n} ${unite}`;
    }
    const unite = nbTroncons > 0 ? `segment${n > 1 ? "s" : ""}` : `ax${n > 1 ? "es" : "is"}`;
    return `${n} ${unite}`;
  };

  const tronconsTries = troncsAxes.slice().sort((a, b) => a.id - b.id);

  const tousLesSous = troncsAxes.flatMap((tr) =>
    (tr.sous_troncons ?? []).map((s) => ({ ...s, parentId: tr.id, parentNom: tr.nom })),
  );
  const pointChaud = tousLesSous
    .filter((s) => s.classe_congestion === "congestionne")
    .sort((a, b) => (b.couleur_google?.pourcentage_rouge ?? 0) - (a.couleur_google?.pourcentage_rouge ?? 0))[0] ?? null;

  return (
    <div className="flex flex-col gap-fluid-4 pb-96">
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

      {/* ── Point chaud ── */}
      {pointChaud && (
        <button
          type="button"
          onClick={() => onSelectionnerSous?.(pointChaud.id, pointChaud.parentId)}
          className="paa-card flex items-start gap-3 p-3 text-left transition-colors hover:bg-paa-blue-50 dark:hover:bg-paa-navy-700"
          style={{
            borderLeft: `4px solid ${couleurClasseCongestion(pointChaud.classe_congestion)}`,
          }}
        >
          <div
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
            style={{
              backgroundColor: `${couleurClasseCongestion(pointChaud.classe_congestion)}22`,
            }}
          >
            <span className="text-lg" aria-hidden>⚠</span>
          </div>
          <div className="min-w-0 flex-1">
            <p
              className="text-fluid-xs font-medium uppercase tracking-wide"
              style={{ color: couleurClasseCongestion(pointChaud.classe_congestion) }}
            >
              {locale === "fr" ? "Point chaud actuel" : "Current hotspot"}
            </p>
            <p className="text-fluid-sm font-semibold text-paa-navy-900 dark:text-paa-blue-100 truncate">
              [{pointChaud.code}] {pointChaud.nom_court}
            </p>
            <p className="text-fluid-xs app-text-muted truncate">{pointChaud.parentNom}</p>
            <p className="text-fluid-xs app-text-muted">
              {pointChaud.couleur_google?.pourcentage_rouge !== null &&
                pointChaud.couleur_google?.pourcentage_rouge !== undefined &&
                `🔴 ${pointChaud.couleur_google.pourcentage_rouge.toFixed(1)}% `}
              {pointChaud.couleur_google?.pourcentage_orange !== null &&
                pointChaud.couleur_google?.pourcentage_orange !== undefined &&
                `· 🟠 ${pointChaud.couleur_google.pourcentage_orange.toFixed(1)}% `}
              {pointChaud.derniere_mesure?.duree_trafic_s != null &&
                `· ${formaterDuree(pointChaud.derniere_mesure.duree_trafic_s)}`}
            </p>
          </div>
        </button>
      )}

      {/* ── Liste des axes — chaque axe dans son propre cadre ── */}
      <div className="flex flex-col gap-2">
        {/* En-tête de section */}
        <div className="flex items-center gap-2 px-1">
          <span className="text-fluid-xs font-semibold uppercase tracking-wider text-paa-navy-600 dark:text-paa-blue-300">
            {locale === "fr"
              ? `${composerLibelle("fr")} surveillés`
              : `${composerLibelle("en")} monitored`}
          </span>
          <span className="flex-1 border-t border-slate-200 dark:border-paa-navy-600" />
        </div>

        {/* Cards par axe */}
        <ul className="flex flex-col gap-2">
          {tronconsTries.map((tr) => {
            const aSousTroncons = (tr.sous_troncons ?? []).length > 0;
            const couleur = aSousTroncons
              ? "#1F4E79"
              : couleurClasseCongestion(tr.classe_congestion ?? "indetermine");
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
                {/* ─── Cadre unique axe + sous-tronçons ─── */}
                <div
                  className={clsx(
                    "overflow-hidden rounded-xl border transition-all duration-200",
                    actif
                      ? "border-paa-blue-400 shadow-lg ring-2 ring-paa-blue-200/60 dark:border-paa-blue-500 dark:ring-paa-blue-700/40"
                      : "border-slate-200 shadow-sm hover:border-paa-blue-200 hover:shadow-md dark:border-paa-navy-600 dark:hover:border-paa-blue-700",
                  )}
                  style={{
                    borderLeftWidth: 4,
                    borderLeftStyle: "solid",
                    borderLeftColor: couleur,
                  }}
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
                    {/* Ligne : pastille + nom */}
                    <div className="flex items-center gap-3">
                      <span
                        className="inline-block h-3.5 w-3.5 shrink-0 rounded-full shadow-sm ring-2 ring-white dark:ring-paa-navy-900"
                        style={{ backgroundColor: couleur }}
                        aria-hidden
                      />
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-fluid-sm font-bold text-paa-navy-900 dark:text-paa-blue-50">
                          {tr.nom}
                        </div>
                      </div>
                    </div>

                    {/* Contenu sous le nom */}
                    {aSousTroncons ? (
                      <div className="ml-6 mt-1.5 flex items-baseline gap-2">
                        <span className="text-fluid-xs app-text-muted">
                          {locale === "fr" ? "Temps total" : "Total time"}
                        </span>
                        <span className="text-fluid-base font-extrabold text-paa-navy-800 dark:text-paa-blue-100">
                          {dureeTrafic}
                        </span>
                        <span className="text-[10px] app-text-muted">
                          ({locale === "fr" ? "somme des tronçons" : "sum of segments"})
                        </span>
                      </div>
                    ) : (
                      <div className="ml-6 mt-2">
                        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-fluid-xs app-text-muted">
                          <span className="font-bold" style={{ color: couleur }}>
                            {tr.libelle_classe ??
                              libelleClasseCongestion(
                                tr.classe_congestion ?? "indetermine",
                                locale,
                              )}
                          </span>
                          <span>
                            {locale === "fr" ? "Temps actuel " : "Current "}
                            <span className="font-extrabold text-paa-navy-900 dark:text-paa-blue-100">
                              {dureeTrafic}
                            </span>
                          </span>
                        </div>
                        {(pctR !== null && pctR !== undefined) ||
                        (pctO !== null && pctO !== undefined) ? (
                          <>
                            <div className="mt-2 flex h-2 w-full overflow-hidden rounded-full bg-gray-200 shadow-inner dark:bg-slate-700">
                              <div
                                className="transition-all duration-500"
                                style={{ width: `${pctR ?? 0}%`, backgroundColor: "#E74C3C" }}
                              />
                              <div
                                className="transition-all duration-500"
                                style={{ width: `${pctO ?? 0}%`, backgroundColor: "#F39C12" }}
                              />
                              <div
                                className="transition-all duration-500"
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
                        <div className="mt-1 truncate text-fluid-xs app-text-muted">
                          {libelleSource(tr.derniere_mesure?.source)} ·{" "}
                          {formaterHeureAbidjan(horoMesure)}
                        </div>
                      </div>
                    )}
                  </button>

                  {/* Sous-tronçons codifiés — à l'intérieur du même cadre */}
                  {(tr.sous_troncons ?? []).length > 0 && (
                    <ul className="border-t border-slate-100 bg-slate-50/60 dark:border-paa-navy-700 dark:bg-paa-navy-900/30">
                      {(tr.sous_troncons ?? []).map((sous) => {
                        const couleurSous = couleurClasseCongestion(sous.classe_congestion);
                        const actifSous = selectionSousId === sous.id;
                        const dureeSous = formaterDuree(sous.derniere_mesure?.duree_trafic_s);
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
                              style={
                                actifSous
                                  ? { borderLeft: `3px solid ${couleurSous}` }
                                  : undefined
                              }
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
                                <span
                                  className="shrink-0 text-[0.7rem] font-semibold"
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

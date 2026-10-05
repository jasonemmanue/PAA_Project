"use client";

/**
 * Fiche d'information de l'axe ou du tronçon sélectionné sur la carte.
 *
 * Remplace les popups Leaflet, qui s'ouvraient sur le tracé cliqué et le
 * masquaient. La fiche est un encart fixe dans un coin de la carte ; le zoom
 * de sélection réserve sa place (`paddingBottomRight` / `paddingTopLeft`)
 * pour que le tracé reste entièrement visible.
 */

import Link from "next/link";

import { BadgeSensAxe, nomCourtAxe } from "@/components/carte/SensAxe";
import {
  couleurClasseCongestion,
  formaterDuree,
  formaterHeureAbidjan,
  libelleClasseCongestion,
} from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { CouleurGoogle, EtatSousTronconCarte, EtatTronconCarte } from "@/lib/types";

type Props = {
  axe: EtatTronconCarte;
  sous: EtatSousTronconCarte | null;
  /** Fiche en bas pleine largeur (mobile) ou en haut à droite (desktop). */
  compacte: boolean;
  onFermer: () => void;
};

export function FicheSelection({ axe, sous, compacte, onFermer }: Props) {
  const { t, locale } = useI18n();

  return (
    <div
      className={
        compacte
          ? "absolute inset-x-2 bottom-2 z-[1060] max-h-[45%] overflow-y-auto"
          : "absolute right-2 top-11 z-[1060] max-h-[calc(100%-3.5rem)] w-[300px] overflow-y-auto"
      }
    >
      <div className="rounded-lg border border-slate-200 bg-white/95 p-3 shadow-paa-md backdrop-blur-sm dark:border-paa-navy-600 dark:bg-paa-navy-900/95">
        <div className="mb-1 flex items-start gap-2">
          <div className="min-w-0 flex-1">
            {sous ? (
              <>
                <p className="truncate text-[11px] app-text-muted">{axe.nom}</p>
                <p className="text-fluid-sm font-bold text-paa-navy-900 dark:text-paa-blue-50">
                  {sous.sens_symbole && <span className="mr-1">{sous.sens_symbole}</span>}
                  {sous.code} — {sous.nom_court}
                </p>
              </>
            ) : (
              <p className="text-fluid-sm font-bold leading-snug text-paa-navy-900 dark:text-paa-blue-50">
                {axe.nom}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onFermer}
            aria-label={t("carte.fiche.fermer")}
            className="-mr-1 -mt-1 rounded p-1 text-lg leading-none app-text-muted hover:bg-slate-100 dark:hover:bg-paa-navy-700"
          >
            ×
          </button>
        </div>

        {/* Direction de l'axe : sens + origine ➜ destination */}
        <div className="mb-2 flex flex-wrap items-center gap-1.5 text-[11px]">
          <BadgeSensAxe sens={axe.sens_axe} />
          <span className="font-medium text-paa-navy-700 dark:text-paa-blue-200">
            {t("carte.fiche.direction")} : {nomCourtAxe(axe).replace(" → ", " ➜ ")}
          </span>
        </div>

        {sous ? <ContenuTroncon sous={sous} /> : <ContenuAxe axe={axe} />}

        <Link
          href={`/indicateurs?troncon=${axe.id}`}
          className="mt-2 block text-[11px] font-semibold text-paa-navy-700 hover:underline dark:text-paa-blue-200"
        >
          {t("carte.fiche.voirIndicateurs")} →
        </Link>
      </div>
    </div>
  );

  function ContenuAxe({ axe }: { axe: EtatTronconCarte }) {
    // Un axe découpé n'a de classe propre que si le backend expose `classe_axe`
    // (§ 39) ; sinon aucune pastille d'état n'est affichée pour l'axe.
    const classe = axe.classe_axe ?? axe.classe_congestion ?? null;
    const nbSous = axe.sous_troncons?.length ?? 0;
    const duree = axe.derniere_mesure?.duree_trafic_s ?? null;
    const reference = axe.temps_reference_50kmh_s ?? null;
    return (
      <>
        {classe && <BadgeClasse classe={classe} />}
        <table className="mt-2 w-full text-[12px]">
          <tbody>
            <Ligne
              libelle={nbSous > 0 ? t("carte.axes.tempsTotal") : t("carte.axes.tempsActuel")}
              valeur={formaterDuree(duree)}
              fort
            />
            <Ligne libelle={t("carte.fiche.reference")} valeur={formaterDuree(reference)} />
            {duree !== null && reference ? (
              <Ligne libelle={t("carte.fiche.ecartReference")} valeur={`×${(duree / reference).toFixed(2)}`} />
            ) : null}
            <Ligne libelle={t("carte.fiche.distance")} valeur={axe.distance_km != null ? `${axe.distance_km} km` : "—"} />
            {nbSous > 0 && (
              <Ligne
                libelle={t("carte.fiche.tronconsCongestionnes")}
                valeur={`${
                  axe.nb_troncons_congestionnes
                  ?? (axe.sous_troncons ?? []).filter((s) => s.classe_congestion === "congestionne").length
                } / ${nbSous}`}
              />
            )}
            {nbSous > 0 && axe.pct_distance_congestionnee != null && (
              <Ligne
                libelle={t("carte.axes.distanceCongestionnee")}
                valeur={`${axe.pct_distance_congestionnee.toFixed(0)} %`}
              />
            )}
          </tbody>
        </table>
        {nbSous === 0 && <CouleursGoogle couleurs={axe.couleur_google} />}
        {nbSous > 0 && axe.classe_axe && (
          <p className="mt-1.5 text-[10px] app-text-muted">
            {t("carte.fiche.regleAxe")}
          </p>
        )}
      </>
    );
  }

  function ContenuTroncon({ sous }: { sous: EtatSousTronconCarte }) {
    return (
      <>
        <BadgeClasse classe={sous.classe_congestion} />
        {sous.motif_congestion && (
          <p className="mt-1 text-[11px] app-text-muted">{sous.motif_congestion}</p>
        )}
        <table className="mt-2 w-full text-[12px]">
          <tbody>
            <Ligne libelle={t("carte.axes.tempsActuel")} valeur={formaterDuree(sous.derniere_mesure?.duree_trafic_s)} fort />
            <Ligne libelle={t("carte.fiche.reference")} valeur={formaterDuree(sous.temps_reference_50kmh_s)} />
            <Ligne libelle={t("carte.fiche.distance")} valeur={sous.distance_km != null ? `${sous.distance_km.toFixed(2)} km` : "—"} />
            <Ligne
              libelle={t("carte.fiche.mesureA")}
              valeur={formaterHeureAbidjan(
                sous.derniere_mesure?.horodatage_local ?? sous.derniere_mesure?.horodatage_utc,
              )}
            />
          </tbody>
        </table>
        <CouleursGoogle couleurs={sous.couleur_google} />
      </>
    );
  }

  function BadgeClasse({ classe }: { classe: EtatSousTronconCarte["classe_congestion"] }) {
    return (
      <span
        className="inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold text-white"
        style={{ backgroundColor: couleurClasseCongestion(classe) }}
      >
        {libelleClasseCongestion(classe, locale)}
      </span>
    );
  }
}

function Ligne({ libelle, valeur, fort = false }: { libelle: string; valeur: string; fort?: boolean }) {
  return (
    <tr>
      <td className="py-0.5 pr-2 app-text-muted">{libelle}</td>
      <td className={`py-0.5 text-right tabular-nums ${fort ? "font-bold text-paa-navy-900 dark:text-paa-blue-50" : ""}`}>
        {valeur}
      </td>
    </tr>
  );
}

function CouleursGoogle({ couleurs }: { couleurs?: CouleurGoogle }) {
  const r = couleurs?.pourcentage_rouge;
  const o = couleurs?.pourcentage_orange;
  const v = couleurs?.pourcentage_vert;
  if (r == null && o == null && v == null) return null;
  return (
    <>
      <div className="mt-2 flex h-2 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-slate-700">
        <div style={{ width: `${r ?? 0}%`, backgroundColor: "#E74C3C" }} />
        <div style={{ width: `${o ?? 0}%`, backgroundColor: "#F39C12" }} />
        <div style={{ width: `${v ?? 0}%`, backgroundColor: "#16a34a" }} />
      </div>
      <div className="mt-1 flex gap-2 text-[11px] app-text-muted">
        {r != null && <span style={{ color: "#E74C3C" }}>🔴 {r.toFixed(1)}%</span>}
        {o != null && <span style={{ color: "#F39C12" }}>🟠 {o.toFixed(1)}%</span>}
        {v != null && <span style={{ color: "#16a34a" }}>🟢 {v.toFixed(1)}%</span>}
      </div>
    </>
  );
}

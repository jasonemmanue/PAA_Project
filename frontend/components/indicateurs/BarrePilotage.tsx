"use client";

/**
 * Barre de pilotage : statut du robot de collecte + boutons start/stop +
 * boutons d'export CSV / XLSX des mesures.
 *
 * Le statut est récupéré toutes les 30 secondes pour rester à jour.
 *
 * Comportement de la pastille :
 *   - rouge gris  : scheduler arrêté (statut.actif = false)
 *   - vert pulse  : scheduler vivant ET heure courante dans la plage [start,end[
 *   - bleu calme  : scheduler vivant mais HORS plage horaire (nuit, 19h→7h)
 * Cela reflète fidèlement le CronTrigger backend (cf. scheduler.py — le job
 * ne se déclenche qu'entre `COLLECT_START_HOUR` et `COLLECT_END_HOUR - 1`).
 */

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/lib/i18n";
import type { CollecteStatus, Troncon } from "@/lib/types";
import type { Periode } from "@/components/indicateurs/Selecteurs";

const FENETRES_JOURS: Record<Periode, number> = {
  "24h": 1,
  "7j": 7,
  "30j": 30,
  "90j": 90,
  "6mois": 180,
  "1an": 365,
};

// ---------------------------------------------------------------------------
// Helpers de fuseau — Africa/Abidjan (UTC+0, pas de DST)
// ---------------------------------------------------------------------------

/** Heure courante (0-23) telle qu'elle est vue à Abidjan, à partir d'un Date. */
function heureAbidjan(d: Date): number {
  const h = new Intl.DateTimeFormat("en-US", {
    timeZone: "Africa/Abidjan",
    hour: "numeric",
    hour12: false,
  }).format(d);
  return parseInt(h, 10);
}

/** Date locale Abidjan au format YYYY-MM-DD (pour comparer "aujourd'hui" / "demain"). */
function dateKeyAbidjan(d: Date): string {
  return new Intl.DateTimeFormat("fr-CA", {
    timeZone: "Africa/Abidjan",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(d);
}

/**
 * Parse la plage horaire renvoyée par le backend :
 *   - `"7h-19h (Africa/Abidjan)"` → `{ debut: 7, fin: 19 }`
 *   - `"24h/24 (Africa/Abidjan)"` → `{ debut: 0, fin: 24 }`
 *
 * Renvoie null si le format est inattendu.
 */
function parserPlage(plage: string | undefined): { debut: number; fin: number } | null {
  if (!plage) return null;
  // Cas spécial : collecte continue 24h/24
  if (/24h\s*\/\s*24/.test(plage)) {
    return { debut: 0, fin: 24 };
  }
  const m = /(\d{1,2})h-(\d{1,2})h/.exec(plage);
  if (!m) return null;
  return { debut: parseInt(m[1], 10), fin: parseInt(m[2], 10) };
}

/**
 * Formate `prochaine_execution` (ISO UTC) en libellé lisible Africa/Abidjan :
 *   - "aujourd'hui 18:40"
 *   - "demain 07:00"
 *   - "23/06 07:00" (au-delà)
 */
function formaterProchainCycle(
  iso: string | null,
  locale: "fr" | "en",
  labels: { aujourdhui: string; demain: string },
): string {
  if (!iso) return "—";
  const cible = new Date(iso);
  if (Number.isNaN(cible.getTime())) return "—";
  const localeIntl = locale === "fr" ? "fr-FR" : "en-GB";

  const heure = new Intl.DateTimeFormat(localeIntl, {
    timeZone: "Africa/Abidjan",
    hour: "2-digit",
    minute: "2-digit",
  }).format(cible);

  const maintenant = new Date();
  const keyCible = dateKeyAbidjan(cible);
  const keyAujourdHui = dateKeyAbidjan(maintenant);
  const keyDemain = dateKeyAbidjan(new Date(maintenant.getTime() + 24 * 3600 * 1000));

  if (keyCible === keyAujourdHui) return `${labels.aujourdhui} ${heure}`;
  if (keyCible === keyDemain) return `${labels.demain} ${heure}`;
  return new Intl.DateTimeFormat(localeIntl, {
    timeZone: "Africa/Abidjan",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(cible);
}

// ---------------------------------------------------------------------------
// Composant
// ---------------------------------------------------------------------------

export function BarrePilotage({
  tronconId,
  troncons = [],
  periode = "24h",
}: {
  tronconId: number | null;
  troncons?: Troncon[];
  periode?: Periode;
}) {
  const { t, locale } = useI18n();
  const { peutEcrire } = useAuth();
  const [statut, setStatut] = useState<CollecteStatus | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  // `tick` force un re-render à chaque minute — sans ça, la pastille resterait
  // verte à 19h00 jusqu'au prochain rafraîchissement du statut (30 s).
  const [, setTick] = useState(0);

  const recharger = async () => {
    try {
      const s = await api.collecteStatus();
      setStatut(s);
      setErreur(null);
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    }
  };

  useEffect(() => {
    recharger();
    const idStatut = setInterval(recharger, 30_000);
    const idTick = setInterval(() => setTick((n) => n + 1), 60_000);
    return () => {
      clearInterval(idStatut);
      clearInterval(idTick);
    };
  }, []);

  const basculer = async () => {
    if (!statut || enCours) return;
    setEnCours(true);
    try {
      const next = statut.actif
        ? await api.collecteStop()
        : await api.collecteStart();
      setStatut(next);
      setErreur(null);
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setEnCours(false);
    }
  };

  // État dérivé : actif + dans la plage horaire ?
  const actif = statut?.actif === true;
  const plage = parserPlage(statut?.config.plage_horaire);
  const heureLocale = heureAbidjan(new Date());
  const enPlage =
    actif && plage !== null && heureLocale >= plage.debut && heureLocale < plage.fin;

  const lblStatut = !actif
    ? t("indicateurs.modePlanifieInactif")
    : enPlage
      ? t("indicateurs.modePlanifieActif")
      : t("indicateurs.modePlanifieVeille");

  const classePastille = !actif
    ? "bg-statut-indetermine"
    : enPlage
      ? "bg-statut-fluide animate-pulse"
      : "bg-paa-blue-400";

  const lblBouton = actif
    ? t("indicateurs.btnArreterCollecte")
    : t("indicateurs.btnDemarrerCollecte");

  const prochainCycle = formaterProchainCycle(
    statut?.prochaine_execution ?? null,
    locale,
    {
      aujourdhui: t("indicateurs.aujourdhui"),
      demain: t("indicateurs.demain"),
    },
  );

  // Calcul de la plage de dates selon la période sélectionnée
  const finDate = new Date();
  const debutDate = new Date();
  debutDate.setDate(finDate.getDate() - FENETRES_JOURS[periode]);
  const debutExport = debutDate.toISOString().slice(0, 10);
  const finExport = finDate.toISOString().slice(0, 10);
  const suffixeFichier = `${debutExport}_${finExport}`;

  const urlCsv = api.urlExportMesures({
    troncon_id: tronconId ?? undefined,
    debut: debutExport,
    fin: finExport,
    format: "csv",
  });
  const urlXlsx = api.urlExportMesures({
    troncon_id: tronconId ?? undefined,
    debut: debutExport,
    fin: finExport,
    format: "xlsx",
  });

  return (
    <section
      aria-label="Pilotage"
      className="paa-card flex flex-col gap-3 p-fluid-4 md:flex-row md:items-center md:justify-between"
    >
      {/* Bloc statut */}
      <div className="flex flex-col gap-1">
        <span className="text-fluid-xs font-medium app-text-muted">
          {t("indicateurs.modePlanifie")}
        </span>
        <div className="flex items-center gap-2">
          <span
            className={`inline-block h-2.5 w-2.5 rounded-full ${classePastille}`}
            aria-hidden
          />
          <span className="text-fluid-base font-semibold text-paa-navy-900 dark:text-paa-blue-100">
            {lblStatut}
          </span>
        </div>
        {statut && (
          <>
            <span className="text-fluid-xs app-text-muted">
              {statut.compteurs_jour.nb_succes} /{" "}
              {statut.config.estimation_requetes_google_par_jour} req/j
              {statut.compteurs_jour.nb_entites_mesurees != null &&
                ` · ${statut.compteurs_jour.nb_entites_mesurees} entités/cycle`}
            </span>
            {plage && (
              <span className="text-fluid-xs app-text-muted">
                {t("indicateurs.plageActive")} :{" "}
                {plage.debut === 0 && plage.fin === 24
                  ? "24h/24 (Africa/Abidjan)"
                  : `${plage.debut}h–${plage.fin}h (Africa/Abidjan)`}
              </span>
            )}
            {statut.prochaine_execution && (
              <span className="text-fluid-xs app-text-muted">
                {t("indicateurs.prochainCycle")} : {prochainCycle}
              </span>
            )}
          </>
        )}
        {erreur && (
          <span className="text-fluid-xs text-statut-congestionne">{erreur}</span>
        )}
      </div>

      {/* Bloc boutons */}
      <div className="flex flex-wrap items-center gap-2">
        {peutEcrire && (
          <button
            type="button"
            onClick={basculer}
            disabled={enCours || statut === null}
            className={actif ? "btn-secondary" : "btn-primary"}
          >
            {enCours ? t("common.loading") : lblBouton}
          </button>
        )}
        {peutEcrire && (
          <a href={urlCsv} className="btn-secondary" download>
            {t("indicateurs.btnExportCsv")}
          </a>
        )}
        {peutEcrire && (
          <a href={urlXlsx} className="btn-secondary" download>
            {t("indicateurs.btnExportXlsx")}
          </a>
        )}
        {peutEcrire && troncons.length > 1 && (
          <>
            {/* Fichier unique : tous les tronçons sur la période sélectionnée */}
            <a
              href={api.urlExportMesures({ debut: debutExport, fin: finExport, format: "csv" })}
              download={`mesures_tous_troncons_${suffixeFichier}.csv`}
              className="btn-secondary"
              title={`Télécharger un CSV unique avec tous les tronçons (${periode})`}
            >
              {t("indicateurs.btnExportTousCsv")}
            </a>
            <a
              href={api.urlExportMesures({ debut: debutExport, fin: finExport, format: "xlsx" })}
              download={`mesures_tous_troncons_${suffixeFichier}.xlsx`}
              className="btn-secondary"
              title={`Télécharger un Excel unique avec tous les tronçons (${periode})`}
            >
              {t("indicateurs.btnExportTousXlsx")}
            </a>
          </>
        )}
      </div>
    </section>
  );
}

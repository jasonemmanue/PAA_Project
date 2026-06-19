"use client";

/**
 * Barre de pilotage : statut du robot de collecte + boutons start/stop +
 * boutons d'export CSV / XLSX des mesures.
 *
 * Le statut est récupéré toutes les 30 secondes pour rester à jour.
 */

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { CollecteStatus } from "@/lib/types";

export function BarrePilotage({
  tronconId,
}: {
  tronconId: number | null;
}) {
  const { t } = useI18n();
  const [statut, setStatut] = useState<CollecteStatus | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

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
    const id = setInterval(recharger, 30_000);
    return () => clearInterval(id);
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

  const actif = statut?.actif === true;
  const lblStatut = actif
    ? t("indicateurs.modePlanifieActif")
    : t("indicateurs.modePlanifieInactif");
  const lblBouton = actif
    ? t("indicateurs.btnArreterCollecte")
    : t("indicateurs.btnDemarrerCollecte");

  // Date du jour au format ISO pour les exports
  const aujourdHui = new Date().toISOString().slice(0, 10);
  const urlCsv = api.urlExportMesures({
    troncon_id: tronconId ?? undefined,
    debut: aujourdHui,
    format: "csv",
  });
  const urlXlsx = api.urlExportMesures({
    troncon_id: tronconId ?? undefined,
    debut: aujourdHui,
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
            className={`inline-block h-2.5 w-2.5 rounded-full ${
              actif ? "bg-statut-fluide animate-pulse" : "bg-statut-indetermine"
            }`}
            aria-hidden
          />
          <span className="text-fluid-base font-semibold text-paa-navy-900 dark:text-paa-blue-100">
            {lblStatut}
          </span>
        </div>
        {statut && (
          <span className="text-fluid-xs app-text-muted">
            {statut.compteurs_jour.nb_succes} /{" "}
            {statut.config.estimation_requetes_google_par_jour} req/j
          </span>
        )}
        {erreur && (
          <span className="text-fluid-xs text-statut-congestionne">{erreur}</span>
        )}
      </div>

      {/* Bloc boutons */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={basculer}
          disabled={enCours || statut === null}
          className={
            actif
              ? "btn-secondary"
              : "btn-primary"
          }
        >
          {enCours ? t("common.loading") : lblBouton}
        </button>
        <a href={urlCsv} className="btn-secondary" download>
          {t("indicateurs.btnExportCsv")}
        </a>
        <a href={urlXlsx} className="btn-secondary" download>
          {t("indicateurs.btnExportXlsx")}
        </a>
      </div>
    </section>
  );
}

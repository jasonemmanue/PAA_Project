"use client";

import { useCallback, useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Cell,
} from "recharts";

import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { CreneauHoraire, HeureOptimaleResponse, Troncon } from "@/lib/types";

type TypeJour = "jour_ouvrable" | "week_end" | "tous";

function formatMn(s: number): string {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${String(sec).padStart(2, "0")} min`;
}

function BadgeSource({ source }: { source: string }) {
  const { t } = useI18n();
  const label =
    source === "profils_horaires"
      ? t("heureOptimale.sourceProfilsHoraires")
      : t("heureOptimale.sourceMesures30j");
  return (
    <span className="inline-block rounded bg-paa-blue-100 px-2 py-0.5 text-fluid-xs text-paa-navy-700 dark:bg-paa-navy-800 dark:text-paa-blue-200">
      {label}
    </span>
  );
}

function CarteTop3({ creneaux, refMn }: { creneaux: CreneauHoraire[]; refMn: number | null }) {
  const { t } = useI18n();
  return (
    <Card titre={t("heureOptimale.top3Titre")} description={t("heureOptimale.top3Desc")}>
      <div className="flex flex-wrap gap-3">
        {creneaux.map((c, i) => (
          <div
            key={c.heure}
            className={`flex flex-col rounded-xl border-2 px-4 py-3 min-w-[120px] ${
              i === 0
                ? "border-green-500 bg-green-50 dark:bg-green-950/30"
                : "border-paa-blue-300 bg-paa-blue-50 dark:border-paa-navy-600 dark:bg-paa-navy-800/40"
            }`}
          >
            <span className="text-fluid-sm font-bold text-paa-navy-700 dark:text-paa-blue-200">
              {c.tranche}
            </span>
            <span className="text-fluid-lg font-extrabold text-paa-navy-900 dark:text-white">
              {c.moyen_mn} min
            </span>
            <span className="text-fluid-xs app-text-muted">
              {t("heureOptimale.colMin")}: {c.min_mn} / {t("heureOptimale.colMax")}: {c.max_mn}
            </span>
          </div>
        ))}
        {refMn !== null && (
          <div className="flex flex-col justify-center rounded-xl border border-dashed border-gray-400 px-4 py-3 min-w-[120px] text-center">
            <span className="text-fluid-xs app-text-muted">{t("heureOptimale.ref50")}</span>
            <span className="text-fluid-sm font-semibold text-gray-600 dark:text-gray-300">
              {refMn} min
            </span>
          </div>
        )}
      </div>
    </Card>
  );
}

function GraphiqueCreneaux({
  creneaux,
  refMn,
}: {
  creneaux: CreneauHoraire[];
  refMn: number | null;
}) {
  const { t } = useI18n();

  const data = creneaux.map((c) => ({
    tranche: c.tranche.split("-")[0], // "07h"
    moyen_mn: c.moyen_mn,
    min_mn: c.min_mn,
    max_mn: c.max_mn,
    optimal: c.optimal,
  }));

  return (
    <Card
      titre={t("heureOptimale.tableauTitre")}
      description={`${t("heureOptimale.colMoyen")} en minutes — barres vertes = créneaux optimaux`}
    >
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-700" />
            <XAxis dataKey="tranche" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} unit=" min" />
            <Tooltip
              formatter={(v: number) => [`${v} min`, t("heureOptimale.colMoyen")]}
              labelFormatter={(l) => `${l}`}
            />
            {refMn !== null && (
              <ReferenceLine
                y={refMn}
                stroke="#9ca3af"
                strokeDasharray="4 4"
                label={{ value: "50 km/h", position: "insideTopRight", fontSize: 10, fill: "#9ca3af" }}
              />
            )}
            <Bar dataKey="moyen_mn" radius={[4, 4, 0, 0]}>
              {data.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.optimal ? "#22c55e" : "#3b82f6"}
                  fillOpacity={entry.optimal ? 1 : 0.7}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

function TableauCreneaux({ creneaux }: { creneaux: CreneauHoraire[] }) {
  const { t } = useI18n();
  return (
    <Card titre="" description="">
      <div className="overflow-x-auto">
        <table className="min-w-full text-fluid-sm">
          <thead className="bg-paa-navy-700 text-white dark:bg-paa-navy-800">
            <tr>
              {[
                t("heureOptimale.colHeure"),
                t("heureOptimale.colMoyen"),
                t("heureOptimale.colMin"),
                t("heureOptimale.colMax"),
                t("heureOptimale.colMesures"),
                "",
              ].map((h) => (
                <th
                  key={h}
                  className="px-3 py-2 text-left text-fluid-xs font-medium uppercase tracking-wide"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {creneaux.map((c) => (
              <tr key={c.heure} className={`border-t app-border ${c.optimal ? "bg-green-50 dark:bg-green-950/20" : ""}`}>
                <td className="px-3 py-2 font-mono font-semibold text-paa-navy-900 dark:text-paa-blue-100">
                  {c.tranche}
                </td>
                <td className="px-3 py-2 font-semibold text-paa-navy-900 dark:text-paa-blue-100">
                  {c.moyen_mn} min
                </td>
                <td className="px-3 py-2 app-text-muted">{c.min_mn} min</td>
                <td className="px-3 py-2 app-text-muted">{c.max_mn} min</td>
                <td className="px-3 py-2 app-text-muted">{c.nb_mesures}</td>
                <td className="px-3 py-2">
                  {c.optimal && (
                    <span className="inline-block rounded bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900/40 dark:text-green-300">
                      ✓ {t("heureOptimale.optimal")}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export function PageHeureOptimale() {
  const { t } = useI18n();
  const [troncons, setTroncons] = useState<Troncon[]>([]);
  const [tronconId, setTronconId] = useState<number | null>(null);
  const [typeJour, setTypeJour] = useState<TypeJour>("jour_ouvrable");
  const [resultat, setResultat] = useState<HeureOptimaleResponse | null>(null);
  const [chargement, setChargement] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  // Charger les tronçons au montage
  useEffect(() => {
    api.troncons()
      .then((list) => {
        // Accepte tous les tronçons non explicitement désactivés
        const liste = Array.isArray(list) ? list.filter((tr) => tr.actif !== false) : [];
        setTroncons(liste);
        if (liste.length > 0) setTronconId(liste[0].id);
      })
      .catch(() => setErreur("Impossible de charger les tronçons depuis l'API."));
  }, []);

  const charger = useCallback(async () => {
    if (tronconId === null) return;
    setChargement(true);
    setErreur(null);
    try {
      const res = await api.heureOptimale(tronconId, typeJour);
      setResultat(res);
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setChargement(false);
    }
  }, [tronconId, typeJour]);

  useEffect(() => {
    charger();
  }, [charger]);

  return (
    <div className="flex flex-col gap-fluid-4">
      <PageHeader
        titre={t("heureOptimale.titre")}
        sousTitre={t("heureOptimale.sousTitre")}
      />

      {/* Sélecteurs */}
      <div className="paa-card flex flex-col gap-3 p-fluid-4 sm:flex-row sm:flex-wrap sm:items-end sm:gap-4">
        <label className="flex w-full flex-col gap-1 sm:w-auto sm:flex-1 sm:min-w-[200px]">
          <span className="text-fluid-xs font-medium app-text-muted">
            {t("heureOptimale.selectTroncon")}
          </span>
          <select
            value={tronconId ?? ""}
            onChange={(e) => setTronconId(Number(e.target.value))}
            className="w-full rounded-md border app-border app-surface px-3 py-2 text-fluid-sm
                       text-paa-navy-900 focus:outline-none focus:ring-2 focus:ring-paa-blue-400
                       dark:text-paa-blue-100 min-h-[40px]"
          >
            {troncons.map((tr) => (
              <option key={tr.id} value={tr.id}>
                {tr.nom}
              </option>
            ))}
          </select>
        </label>

        <label className="flex w-full flex-col gap-1 sm:w-auto sm:min-w-[160px]">
          <span className="text-fluid-xs font-medium app-text-muted">
            {t("heureOptimale.selectTypeJour")}
          </span>
          <select
            value={typeJour}
            onChange={(e) => setTypeJour(e.target.value as TypeJour)}
            className="w-full rounded-md border app-border app-surface px-3 py-2 text-fluid-sm
                       text-paa-navy-900 focus:outline-none focus:ring-2 focus:ring-paa-blue-400
                       dark:text-paa-blue-100 min-h-[40px]"
          >
            <option value="jour_ouvrable">{t("heureOptimale.joursOuvrables")}</option>
            <option value="week_end">{t("heureOptimale.weekEnds")}</option>
            <option value="tous">{t("heureOptimale.tous")}</option>
          </select>
        </label>

        {resultat && (
          <div className="sm:self-end sm:pb-1">
            <BadgeSource source={resultat.source} />
          </div>
        )}
      </div>

      {erreur && (
        <div className="rounded-md border border-statut-congestionne/40 bg-statut-congestionne/10 px-3 py-2 text-fluid-sm text-statut-congestionne">
          Erreur : {erreur}
        </div>
      )}

      {chargement && (
        <p className="text-fluid-xs app-text-muted">{t("common.loading")}</p>
      )}

      {!chargement && resultat && resultat.nb_creneaux === 0 && (
        <div className="paa-card p-fluid-4 text-fluid-sm app-text-muted">
          {t("heureOptimale.aucunCreneau")}
        </div>
      )}

      {!chargement && resultat && resultat.nb_creneaux > 0 && (
        <>
          <CarteTop3
            creneaux={resultat.recommandation}
            refMn={resultat.temps_ref_50kmh_mn}
          />
          <GraphiqueCreneaux
            creneaux={resultat.creneaux}
            refMn={resultat.temps_ref_50kmh_mn}
          />
          <TableauCreneaux creneaux={resultat.creneaux} />
        </>
      )}
    </div>
  );
}

"use client";

import { useI18n } from "@/lib/i18n";
import type { Troncon } from "@/lib/types";

export type FiltresPeriode = "aujourd'hui" | "24h" | "7j";

export interface FiltresEtat {
  type: string;       // "" = tous
  periode: FiltresPeriode;
  troncon_id: number | null;
}

interface Props {
  filtres: FiltresEtat;
  onChange: (f: FiltresEtat) => void;
  troncons: Troncon[];
}

export function FiltresIncidents({ filtres, onChange, troncons }: Props) {
  const { t } = useI18n();

  const types = [
    { value: "",              label: t("incidents.filtreTypeTous") },
    { value: "accident",      label: t("incidents.typeAccident") },
    { value: "embouteillage", label: t("incidents.typeEmbouteillage") },
    { value: "route_barree",  label: t("incidents.typeRouteBarree") },
    { value: "travaux",       label: t("incidents.typeTravaux") },
    { value: "autre",         label: t("incidents.typeAutre") },
  ];

  const periodes: { value: FiltresPeriode; label: string }[] = [
    { value: "aujourd'hui", label: t("incidents.periodAujourd") },
    { value: "24h",         label: t("incidents.period24h") },
    { value: "7j",          label: t("incidents.period7j") },
  ];

  const selectCls =
    "text-sm border border-gray-300 dark:border-gray-600 rounded-md px-3 py-1.5 " +
    "bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none " +
    "focus:ring-2 focus:ring-paa-blue-500";

  return (
    <div className="flex flex-wrap gap-3 items-center py-2">
      {/* Filtre type */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-600 dark:text-gray-400 font-medium">
          {t("incidents.filtreType")}
        </span>
        <select
          className={selectCls}
          value={filtres.type}
          onChange={(e) => onChange({ ...filtres, type: e.target.value })}
        >
          {types.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
      </div>

      {/* Filtre période */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-600 dark:text-gray-400 font-medium">
          {t("incidents.filtrePeriode")}
        </span>
        <select
          className={selectCls}
          value={filtres.periode}
          onChange={(e) =>
            onChange({ ...filtres, periode: e.target.value as FiltresPeriode })
          }
        >
          {periodes.map((p) => (
            <option key={p.value} value={p.value}>{p.label}</option>
          ))}
        </select>
      </div>

      {/* Filtre tronçon */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-600 dark:text-gray-400 font-medium">
          {t("incidents.filtreTroncon")}
        </span>
        <select
          className={selectCls}
          value={filtres.troncon_id ?? ""}
          onChange={(e) =>
            onChange({
              ...filtres,
              troncon_id: e.target.value === "" ? null : Number(e.target.value),
            })
          }
        >
          <option value="">{t("incidents.filtreTronconTous")}</option>
          {troncons.map((tr) => (
            <option key={tr.id} value={tr.id}>{tr.nom}</option>
          ))}
        </select>
      </div>
    </div>
  );
}

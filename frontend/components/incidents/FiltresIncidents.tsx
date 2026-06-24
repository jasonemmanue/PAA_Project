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
  apiBaseUrl: string;
}

// Correspond les valeurs de période UI vers les valeurs de la query string backend
function _periodeVersBackend(p: FiltresPeriode): string {
  if (p === "aujourd'hui") return "1j";
  return p;
}

export function FiltresIncidents({ filtres, onChange, troncons, apiBaseUrl }: Props) {
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

  function construireUrlExport(): string {
    const params = new URLSearchParams();
    params.set("periode", _periodeVersBackend(filtres.periode));
    if (filtres.type) params.set("type_incident", filtres.type);
    if (filtres.troncon_id !== null) params.set("troncon_id", String(filtres.troncon_id));
    return `${apiBaseUrl}/incidents/export?${params.toString()}`;
  }

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

      {/* Bouton export CSV */}
      <a
        href={construireUrlExport()}
        download
        title={t("incidents.exporterCsvTitle")}
        className="ml-auto flex items-center gap-1.5 rounded-md border border-paa-blue-500
                   px-3 py-1.5 text-sm font-medium text-paa-blue-700
                   hover:bg-paa-blue-50 dark:border-paa-blue-400 dark:text-paa-blue-300
                   dark:hover:bg-paa-navy-700 transition-colors"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className="h-4 w-4"
          aria-hidden
        >
          <path
            fillRule="evenodd"
            d="M10 3a.75.75 0 0 1 .75.75v8.69l2.47-2.47a.75.75 0 1 1 1.06 1.06l-3.75 3.75a.75.75 0 0 1-1.06 0L5.72 11.03a.75.75 0 1 1 1.06-1.06l2.47 2.47V3.75A.75.75 0 0 1 10 3ZM3.25 16.5a.75.75 0 0 1 .75-.75h12a.75.75 0 0 1 0 1.5h-12a.75.75 0 0 1-.75-.75Z"
            clipRule="evenodd"
          />
        </svg>
        {t("incidents.exporterCsv")}
      </a>
    </div>
  );
}

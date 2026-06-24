"use client";

import { useState } from "react";
import type { Incident } from "@/lib/types";
import { useI18n } from "@/lib/i18n";

const PAGE_SIZE = 20;

// Couleur du badge type
function couleurBadge(type: string | null): string {
  switch (type) {
    case "accident":      return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
    case "embouteillage": return "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200";
    case "route_barree":  return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200";
    case "travaux":       return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
    default:              return "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300";
  }
}

function ageRelatif(horodatage: string): string {
  const ageMs = Date.now() - new Date(horodatage).getTime();
  const ageH = Math.floor(ageMs / 3600000);
  const ageMin = Math.floor((ageMs % 3600000) / 60000);
  if (ageH >= 24) return `il y a ${Math.floor(ageH / 24)}j`;
  if (ageH > 0)   return `il y a ${ageH}h${ageMin > 0 ? ageMin + "min" : ""}`;
  return `il y a ${ageMin}min`;
}

interface PanneauProps {
  incident: Incident;
  onClose: () => void;
}

function PanneauDetail({ incident: inc, onClose }: PanneauProps) {
  const { t } = useI18n();

  const typeLibelle: Record<string, string> = {
    accident:      t("incidents.typeAccident"),
    embouteillage: t("incidents.typeEmbouteillage"),
    route_barree:  t("incidents.typeRouteBarree"),
    travaux:       t("incidents.typeTravaux"),
    autre:         t("incidents.typeAutre"),
  };

  const severiteLibelle: Record<string, string> = {
    grave:   t("incidents.severiteGrave"),
    moyen:   t("incidents.severiteMoyen"),
    mineur:  t("incidents.severiteMineur"),
    inconnu: t("incidents.severiteInconnu"),
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}>
      <div
        className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-lg w-full p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 mb-4">
          <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">
            {inc.titre}
          </h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl leading-none shrink-0"
          >
            ×
          </button>
        </div>

        <div className="flex flex-wrap gap-2 mb-3">
          {inc.type_incident && (
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${couleurBadge(inc.type_incident)}`}>
              {typeLibelle[inc.type_incident] ?? inc.type_incident}
            </span>
          )}
          {inc.severite && inc.severite !== "inconnu" && (
            <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
              {severiteLibelle[inc.severite] ?? inc.severite}
            </span>
          )}
          {inc.actif && (
            <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-red-500 text-white animate-pulse">
              ACTIF
            </span>
          )}
        </div>

        {inc.resume && (
          <p className="text-sm text-gray-700 dark:text-gray-300 mb-3 leading-relaxed">
            {inc.resume}
          </p>
        )}

        <div className="text-xs text-gray-500 dark:text-gray-400 space-y-1">
          <div>{inc.source_nom} · {ageRelatif(inc.horodatage_publication)}</div>
          {inc.lieu_extrait && <div>📍 {inc.lieu_extrait}</div>}
          {inc.troncon_id && <div>Tronçon #{inc.troncon_id}</div>}
        </div>

        <a
          href={inc.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-4 inline-block text-sm text-paa-blue-600 dark:text-paa-blue-400 hover:underline"
        >
          {t("incidents.voirSource")} →
        </a>
      </div>
    </div>
  );
}

interface Props {
  incidents: Incident[];
}

export function ListeIncidents({ incidents }: Props) {
  const { t } = useI18n();
  const [page, setPage] = useState(0);
  const [selectionne, setSelectionne] = useState<Incident | null>(null);

  const total = incidents.length;
  const debut = page * PAGE_SIZE;
  const page_incidents = incidents.slice(debut, debut + PAGE_SIZE);
  const nbPages = Math.ceil(total / PAGE_SIZE);

  const typeLibelle: Record<string, string> = {
    accident:      t("incidents.typeAccident"),
    embouteillage: t("incidents.typeEmbouteillage"),
    route_barree:  t("incidents.typeRouteBarree"),
    travaux:       t("incidents.typeTravaux"),
    autre:         t("incidents.typeAutre"),
  };

  if (total === 0) {
    return (
      <p className="text-sm text-gray-500 dark:text-gray-400 py-4 text-center">
        {t("incidents.aucunIncident")}
      </p>
    );
  }

  return (
    <>
      {selectionne && (
        <PanneauDetail incident={selectionne} onClose={() => setSelectionne(null)} />
      )}

      <div className="divide-y divide-gray-100 dark:divide-gray-700">
        {page_incidents.map((inc) => (
          <button
            key={inc.id}
            onClick={() => setSelectionne(inc)}
            className="w-full text-left py-3 px-1 flex items-start gap-3 hover:bg-gray-50 dark:hover:bg-gray-800/50 rounded-lg transition-colors"
          >
            {/* Badge type */}
            <span
              className={`shrink-0 text-xs px-2 py-0.5 rounded-full font-medium mt-0.5 ${couleurBadge(inc.type_incident)}`}
            >
              {typeLibelle[inc.type_incident ?? ""] ?? inc.type_incident ?? "—"}
            </span>

            {/* Contenu */}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                {inc.titre}
                {inc.actif && (
                  <span className="ml-2 text-xs bg-red-500 text-white px-1.5 py-0.5 rounded animate-pulse">
                    ACTIF
                  </span>
                )}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                {inc.source_nom} · {ageRelatif(inc.horodatage_publication)}
                {inc.lieu_extrait ? ` · 📍 ${inc.lieu_extrait}` : ""}
              </p>
            </div>
          </button>
        ))}
      </div>

      {/* Pagination */}
      {nbPages > 1 && (
        <div className="flex items-center justify-between pt-4">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="text-sm px-3 py-1 rounded border border-gray-300 dark:border-gray-600 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-700"
          >
            ← Précédent
          </button>
          <span className="text-sm text-gray-500">
            {page + 1} / {nbPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(nbPages - 1, p + 1))}
            disabled={page === nbPages - 1}
            className="text-sm px-3 py-1 rounded border border-gray-300 dark:border-gray-600 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-700"
          >
            Suivant →
          </button>
        </div>
      )}
    </>
  );
}

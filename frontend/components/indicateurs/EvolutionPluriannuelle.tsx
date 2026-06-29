"use client";

/**
 * Évolution pluriannuelle — version dynamique par tronçon.
 *
 * Affiche jusqu'à 3 campagnes côte à côte :
 *  - Les 2 campagnes complètes les plus récentes (depuis evolution_indicateur)
 *  - Le mois calendaire courant, mis à jour en temps réel depuis mesures
 *
 * Source backend : GET /evolution/troncon/{id}
 * Auto-refresh du mois courant toutes les 5 minutes.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useAuth } from "@/contexts/AuthContext";
import { Card } from "@/components/ui/Card";
import { useI18n } from "@/lib/i18n";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8081";

// Intervalle de polling pour le mois courant (5 min)
const POLLING_MS = 5 * 60 * 1000;

type TypeJour = "jours_ouvrables" | "week_ends";

interface BlocStats {
  min_mn: number;
  moyen_mn: number;
  max_mn: number;
  nb_mesures?: number;
}

interface Campagne {
  periode: string;
  periode_label: string;
  source: "historique" | "live";
  debut?: string;
  fin?: string;
  nb_mesures_total?: number;
  jours_ouvrables: BlocStats | null;
  week_ends: BlocStats | null;
}

interface EvolutionTronconResponse {
  troncon_id: number;
  troncon_nom: string;
  a_donnees_historiques: boolean;
  campagnes: Campagne[];
}

interface Props {
  tronconId: number | null;
}

export function EvolutionPluriannuelle({ tronconId }: Props) {
  const { t } = useI18n();
  const { peutEcrire } = useAuth();

  const [data, setData] = useState<EvolutionTronconResponse | null>(null);
  const [chargement, setChargement] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [typeJour, setTypeJour] = useState<TypeJour>("jours_ouvrables");
  const [importEnCours, setImportEnCours] = useState(false);
  const [messageImport, setMessageImport] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const charger = useCallback(async (id: number) => {
    try {
      const rep = await fetch(`${API_BASE}/evolution/troncon/${id}`);
      if (!rep.ok) throw new Error(`HTTP ${rep.status}`);
      const json: EvolutionTronconResponse = await rep.json();
      setData(json);
      setErreur(null);
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setChargement(false);
    }
  }, []);

  useEffect(() => {
    if (tronconId === null) {
      setData(null);
      return;
    }
    setChargement(true);
    charger(tronconId);

    // Polling pour garder le mois courant à jour
    if (pollingRef.current) clearInterval(pollingRef.current);
    pollingRef.current = setInterval(() => charger(tronconId), POLLING_MS);
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [tronconId, charger]);

  async function importerFichier(f: File) {
    setImportEnCours(true);
    setMessageImport(null);
    setErreur(null);
    try {
      const form = new FormData();
      form.append("fichier", f);
      const rep = await fetch(`${API_BASE}/import/evolution-csv`, {
        method: "POST",
        body: form,
      });
      if (!rep.ok) {
        const txt = await rep.text().catch(() => "");
        throw new Error(`HTTP ${rep.status} — ${txt || rep.statusText}`);
      }
      const json = await rep.json();
      setMessageImport(json.message ?? "Import réussi.");
      if (tronconId !== null) await charger(tronconId);
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setImportEnCours(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  // Les 2 campagnes historiques les plus récentes + le mois courant
  const campagnes: Campagne[] = (() => {
    if (!data) return [];
    const historiques = data.campagnes
      .filter((c) => c.source === "historique")
      .slice(-2); // les 2 plus récentes (déjà triées chronologiquement)
    const live = data.campagnes.filter((c) => c.source === "live");
    return [...historiques, ...live];
  })();

  // Données Recharts : 1 objet par campagne avec min/moyen/max du type_jour sélectionné
  const chartData = campagnes.map((c) => {
    const bloc = typeJour === "jours_ouvrables" ? c.jours_ouvrables : c.week_ends;
    return {
      periode: c.periode_label,
      isLive: c.source === "live",
      min: bloc?.min_mn ?? null,
      moyen: bloc?.moyen_mn ?? null,
      max: bloc?.max_mn ?? null,
      nb: bloc?.nb_mesures ?? c.nb_mesures_total ?? 0,
    };
  });

  const aucuneDonnee =
    !chargement && !erreur && campagnes.every((c) => {
      const b = typeJour === "jours_ouvrables" ? c.jours_ouvrables : c.week_ends;
      return b === null;
    });

  return (
    <Card
      titre={t("indicateurs.evolutionTitle")}
      description={t("indicateurs.evolutionSubtitle")}
    >
      {/* Bouton import CSV/Excel — visible en mode écriture */}
      {peutEcrire && (
        <div className="mb-3 flex flex-col gap-2 rounded-md border border-dashed app-border bg-paa-blue-50/50 p-3 dark:bg-paa-navy-800/50 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-fluid-sm font-semibold text-paa-navy-900 dark:text-paa-blue-100">
              📥 Mettre à jour les données pluriannuelles
            </p>
            <p className="text-fluid-xs app-text-muted">
              Format CSV ou Excel à 7 colonnes : axe, sens, periode, type_jour,
              temps_min_s, temps_moyen_s, temps_max_s. Idempotent (UPSERT).
            </p>
          </div>
          <div className="flex items-center gap-2">
            <input
              ref={inputRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              disabled={importEnCours}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) importerFichier(f);
              }}
              className="text-fluid-xs"
            />
            {importEnCours && (
              <span className="text-fluid-xs app-text-muted">Import en cours…</span>
            )}
          </div>
        </div>
      )}

      {messageImport && (
        <div className="mb-3 rounded-md border border-statut-fluide/40 bg-statut-fluide/10 px-3 py-2 text-fluid-xs text-statut-fluide">
          ✅ {messageImport}
        </div>
      )}

      {/* Toggle Jours ouvrables / Week-ends */}
      <div
        role="group"
        className="mb-3 inline-flex flex-wrap gap-1 rounded-md border app-border p-1 app-surface"
      >
        {(["jours_ouvrables", "week_ends"] as const).map((tj) => {
          const actif = typeJour === tj;
          const label =
            tj === "jours_ouvrables"
              ? t("indicateurs.joursOuvrables")
              : t("indicateurs.weekEnds");
          return (
            <button
              key={tj}
              type="button"
              onClick={() => setTypeJour(tj)}
              aria-pressed={actif}
              className={`px-3 py-1.5 text-fluid-xs font-medium rounded transition-colors min-h-[36px] ${
                actif
                  ? "bg-paa-navy-700 text-white"
                  : "text-paa-navy-700 hover:bg-paa-blue-50 dark:text-paa-blue-100 dark:hover:bg-paa-navy-700"
              }`}
            >
              {label}
            </button>
          );
        })}
      </div>

      {/* États de chargement / erreur */}
      {(chargement || tronconId === null) && (
        <div className="flex h-[220px] items-center justify-center text-fluid-sm app-text-muted">
          {tronconId === null ? t("common.noData") : t("common.loading")}
        </div>
      )}
      {erreur && (
        <div className="text-fluid-sm text-statut-congestionne">
          {t("common.error")} : {erreur}
        </div>
      )}
      {!chargement && !erreur && aucuneDonnee && tronconId !== null && (
        <div className="flex h-[220px] items-center justify-center text-fluid-sm app-text-muted">
          {t("common.noData")}
        </div>
      )}

      {/* Graphique */}
      {!chargement && !erreur && !aucuneDonnee && chartData.length > 0 && (
        <>
          <div className="h-[260px] w-full md:h-[320px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={chartData}
                margin={{ top: 5, right: 8, left: -10, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(125,125,125,0.18)" />
                <XAxis
                  dataKey="periode"
                  tick={({ x, y, payload }) => (
                    <g transform={`translate(${x},${y})`}>
                      <text
                        x={0}
                        y={0}
                        dy={14}
                        textAnchor="middle"
                        fontSize={11}
                        fill="currentColor"
                      >
                        {payload.value}
                      </text>
                      {/* Badge "en cours" sous le label de la campagne live */}
                      {chartData.find((d) => d.periode === payload.value)?.isLive && (
                        <text x={0} y={0} dy={28} textAnchor="middle" fontSize={9} fill="#F39C12">
                          ● en cours
                        </text>
                      )}
                    </g>
                  )}
                  height={45}
                />
                <YAxis
                  tick={{ fontSize: 11 }}
                  label={{
                    value: "min",
                    angle: -90,
                    position: "insideLeft",
                    offset: 14,
                    style: { fontSize: 11, fill: "currentColor" },
                  }}
                />
                <Tooltip
                  contentStyle={{
                    background: "rgba(11, 37, 69, 0.96)",
                    border: "none",
                    borderRadius: 6,
                    fontSize: 12,
                    color: "white",
                  }}
                  formatter={(value: unknown, key: string) => {
                    const labels: Record<string, string> = {
                      min: t("indicateurs.evolutionMin"),
                      moyen: t("indicateurs.evolutionMoyen"),
                      max: t("indicateurs.evolutionMax"),
                    };
                    return [`${value} min`, labels[key] ?? key];
                  }}
                  labelFormatter={(label: string) => {
                    const entry = chartData.find((d) => d.periode === label);
                    const suffix = entry?.nb ? ` — ${entry.nb} mesures` : "";
                    return `${label}${suffix}`;
                  }}
                />
                <Legend
                  wrapperStyle={{ fontSize: 12 }}
                  formatter={(v: string) => {
                    const labels: Record<string, string> = {
                      min: t("indicateurs.evolutionMin"),
                      moyen: t("indicateurs.evolutionMoyen"),
                      max: t("indicateurs.evolutionMax"),
                    };
                    return labels[v] ?? v;
                  }}
                />
                <Bar dataKey="min" fill="#2ECC71" radius={[4, 4, 0, 0]} />
                <Bar dataKey="moyen" fill="#F39C12" radius={[4, 4, 0, 0]} />
                <Bar dataKey="max" fill="#E74C3C" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Légende mois courant */}
          {campagnes.some((c) => c.source === "live") && (
            <p className="mt-1 text-fluid-xs app-text-muted text-right">
              ● Mois en cours — données Google actualisées automatiquement
            </p>
          )}

          {/* Message si pas de données historiques pour ce tronçon */}
          {data && !data.a_donnees_historiques && (
            <p className="mt-2 rounded-md border app-border bg-amber-50/50 dark:bg-amber-950/20 px-3 py-2 text-fluid-xs text-amber-700 dark:text-amber-400">
              ℹ️ Pas de campagne historique pour ce tronçon. Seul le mois courant est affiché.
              Les données pluriannuelles sont disponibles uniquement pour les 6 axes officiels DEESP.
            </p>
          )}
        </>
      )}
    </Card>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";

import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { RapportZonesCongestionnees, EntreeCongestion } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8081";

function telechargerPdf(campagne: string, debut?: string, fin?: string, heureDebut = 0, heureFin = 24): void {
  const params = new URLSearchParams({ campagne });
  if (debut) params.set("debut", debut);
  if (fin) params.set("fin", fin);
  if (heureDebut !== 0) params.set("heure_debut", String(heureDebut));
  if (heureFin !== 24) params.set("heure_fin", String(heureFin));
  const url = `${API_BASE}/rapport/zones-congestionnees/pdf?${params.toString()}`;
  const a = document.createElement("a");
  a.href = url;
  a.rel = "noopener noreferrer";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function joursCongesStr(e: EntreeCongestion): string {
  const abrev: Record<string, string> = {
    lundi: "Lun", mardi: "Mar", mercredi: "Mer",
    jeudi: "Jeu", vendredi: "Ven", samedi: "Sam", dimanche: "Dim",
  };
  return Object.entries(e.nb_par_jour_semaine ?? {})
    .map(([j, n]) => `${abrev[j] ?? j}(${n})`)
    .join(", ");
}

function exporterCsv(entrees: EntreeCongestion[], nomFichier: string, typeLabel: string): void {
  const headers = [typeLabel, "JOURS", "TRANCHE HORAIRE", "NB / SEMAINE", "RÈGLE DÉCLENCHÉE"];
  const lignes = entrees.map((e) => {
    const nom = e.sous_troncon_code
      ? `${e.sous_troncon_code} - ${e.sous_troncon_nom ?? ""}`
      : e.troncon_nom;
    const regles: string[] = [];
    if (e.regle_semaine) regles.push("Règle 1 — semaine (>=4 fois)");
    if (e.regle_jour_indicatif) regles.push("Règle 2 — jour indicatif (>=3 fois)");
    return [nom, joursCongesStr(e), e.tranche, String(e.nb_total_semaine), regles.join(" | ")];
  });

  const csv = [headers, ...lignes].map((r) => r.map((c) => `"${c}"`).join(",")).join("\n");
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = nomFichier;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(a.href);
}

function lundiSemaineIso(dateStr: string): string {
  const d = new Date(dateStr + "T12:00:00");
  const jour = d.getDay();
  const diff = jour === 0 ? 6 : jour - 1;
  const lundi = new Date(d.getTime() - diff * 86400000);
  return lundi.toISOString().slice(0, 10);
}

function dimancheSemaineIso(lundiKey: string): string {
  const d = new Date(lundiKey + "T12:00:00");
  const dim = new Date(d.getTime() + 6 * 86400000);
  return dim.toISOString().slice(0, 10);
}

function labelSemaine(lundiKey: string): string {
  const d = new Date(lundiKey + "T12:00:00");
  const dim = new Date(d.getTime() + 6 * 86400000);
  const fmt = (dt: Date) =>
    `${String(dt.getDate()).padStart(2, "0")}/${String(dt.getMonth() + 1).padStart(2, "0")}`;
  return `Sem. ${fmt(d)} – ${fmt(dim)}`;
}

function genererSemainesIso(debut: string, fin: string): string[] {
  const lundis: string[] = [];
  const premierLundi = lundiSemaineIso(debut);
  const dernierLundi = lundiSemaineIso(fin);
  let cur = premierLundi;
  while (cur <= dernierLundi) {
    lundis.push(cur);
    const d = new Date(cur + "T12:00:00");
    d.setDate(d.getDate() + 7);
    cur = d.toISOString().slice(0, 10);
  }
  return lundis;
}

function lundiSemaineActuelle(): string {
  return lundiSemaineIso(new Date().toISOString().slice(0, 10));
}

export function TableauZonesCongestionnees({
  campagne,
  debutRange,
  finRange,
  heureDebut = 0,
  heureFin = 24,
}: {
  campagne: string;
  debutRange: string;
  finRange: string;
  heureDebut?: number;
  heureFin?: number;
}) {
  const [rapport, setRapport] = useState<RapportZonesCongestionnees | null>(null);
  const [chargement, setChargement] = useState(false);
  const [fenetre, setFenetre] = useState(0);

  const semaines = genererSemainesIso(debutRange, finRange);
  const maxFenetre = Math.max(0, semaines.length - 1);
  const lundiActuel = semaines[fenetre] ?? semaines[0] ?? lundiSemaineActuelle();
  const dimancheActuel = dimancheSemaineIso(lundiActuel);
  const labelFen = labelSemaine(lundiActuel);

  // Positionne sur la semaine courante ou la dernière disponible au changement de plage
  useEffect(() => {
    if (semaines.length === 0) return;
    const lundiAuj = lundiSemaineActuelle();
    const idx = semaines.indexOf(lundiAuj);
    setFenetre(idx >= 0 ? idx : semaines.length - 1);
  }, [debutRange, finRange]);

  const charger = useCallback(async () => {
    setChargement(true);
    try {
      const data = await api.rapportZonesCongestionnees(
        campagne, lundiActuel, dimancheActuel, heureDebut, heureFin,
      );
      setRapport(data);
    } catch {
      setRapport(null);
    } finally {
      setChargement(false);
    }
  }, [campagne, lundiActuel, dimancheActuel, heureDebut, heureFin]);

  useEffect(() => {
    charger();
  }, [charger]);

  const entrees = (rapport?.entrees ?? []).filter((e) => e.sous_troncon_id !== null);

  return (
    <Card
      titre="Tableau 16 — Tronçons congestionnés (règles DEESP)"
      description={
        "Un tronçon est congestionné à un créneau horaire si l'une des deux règles DEESP est vérifiée — " +
        "Règle 1 (semaine) : ce créneau revient au moins 4 fois dans la même semaine calendaire ISO (lun–dim) ; " +
        "Règle 2 (jour indicatif) : ce même jour de la semaine (ex. lundi) est congestionné à cette tranche horaire au moins 3 fois dans le mois. " +
        "Critère de congestion d'une mesure : couleur Google Maps — rouge présent OU orange ≥ 50 % du tronçon."
      }
    >
      {/* Navigation par semaine ISO */}
      <div className="mb-3 flex items-center gap-2 text-fluid-xs">
        <button
          type="button"
          disabled={fenetre === 0}
          onClick={() => setFenetre((f) => f - 1)}
          className="px-3 py-1 rounded-md border app-border disabled:opacity-40
                     hover:bg-paa-blue-50 dark:hover:bg-paa-navy-800 transition-colors"
        >
          ← Semaine précédente
        </button>
        <span className="app-text-muted font-medium">
          {labelFen} ({fenetre + 1}/{semaines.length})
        </span>
        <button
          type="button"
          disabled={fenetre >= maxFenetre}
          onClick={() => setFenetre((f) => f + 1)}
          className="px-3 py-1 rounded-md border app-border disabled:opacity-40
                     hover:bg-paa-blue-50 dark:hover:bg-paa-navy-800 transition-colors"
        >
          Semaine suivante →
        </button>
      </div>

      {chargement && (
        <div className="text-fluid-xs app-text-muted animate-pulse mb-3">Chargement du Tableau 16…</div>
      )}

      {/* ──── Tronçons codifiés congestionnés ──── */}
      <div className="overflow-x-auto">
        <table className="min-w-full text-fluid-sm">
          <thead className="bg-paa-navy-700 text-white dark:bg-paa-navy-800">
            <tr>
              <Th>TRONÇON</Th>
              <Th>JOURS</Th>
              <Th>TRANCHE HORAIRE</Th>
              <Th className="text-right">NB / SEMAINE</Th>
              <Th>RÈGLE DÉCLENCHÉE</Th>
            </tr>
          </thead>
          <tbody>
            {entrees.map((e) => (
              <LigneTroncon key={`${e.sous_troncon_id}-${e.troncon_id}-${e.heure}`} e={e} />
            ))}
            {entrees.length === 0 && !chargement && (
              <tr>
                <Td colSpan={5}>
                  <span className="app-text-muted">
                    {rapport
                      ? "Aucun tronçon codifié congestionné sur cette semaine."
                      : "Chargement…"}
                  </span>
                </Td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {entrees.length > 0 && (
        <div className="mt-2 flex justify-end gap-2">
          <BoutonExportCsv
            label="Exporter CSV"
            onClick={() =>
              exporterCsv(entrees, `congestion_troncons_${rapport?.campagne ?? "export"}.csv`, "TRONÇON")
            }
          />
        </div>
      )}

      {/* Bouton PDF */}
      <div className="mt-4 border-t app-border pt-4">
        <BoutonExportPdf
          campagne={rapport?.campagne ?? campagne}
          actif={!!rapport}
          debut={lundiActuel}
          fin={dimancheActuel}
          heureDebut={heureDebut}
          heureFin={heureFin}
        />
      </div>
    </Card>
  );
}

function LigneTroncon({ e }: { e: EntreeCongestion }) {
  const abrev: Record<string, string> = {
    lundi: "Lun", mardi: "Mar", mercredi: "Mer",
    jeudi: "Jeu", vendredi: "Ven", samedi: "Sam", dimanche: "Dim",
  };
  const jours = Object.entries(e.nb_par_jour_semaine ?? {});
  return (
    <tr className="border-t app-border">
      <Td>
        <div className="flex flex-col">
          <span className="font-mono font-semibold">{e.sous_troncon_code}</span>
          <span className="text-fluid-xs app-text-muted">{e.sous_troncon_nom}</span>
        </div>
      </Td>
      <Td>
        <div className="flex flex-wrap gap-1">
          {jours.map(([j, n]) => (
            <span
              key={j}
              className="inline-block rounded bg-statut-congestionne/15 px-1.5 py-0.5 text-xs font-medium text-statut-congestionne"
            >
              {abrev[j] ?? j} ({n})
            </span>
          ))}
        </div>
      </Td>
      <Td className="font-mono">{e.tranche}</Td>
      <Td className="text-right font-semibold">{e.nb_total_semaine}</Td>
      <Td>
        <Regles e={e} />
      </Td>
    </tr>
  );
}

function Regles({ e }: { e: EntreeCongestion }) {
  return (
    <div className="flex flex-col gap-1">
      {e.regle_semaine && (
        <span className="inline-block rounded bg-amber-500/20 px-2 py-0.5 text-xs text-amber-700 dark:text-amber-300">
          Règle 1 — semaine (≥ 4 ×)
        </span>
      )}
      {e.regle_jour_indicatif && (
        <span className="inline-block rounded bg-statut-congestionne/20 px-2 py-0.5 text-xs text-statut-congestionne">
          Règle 2 — jour indicatif (≥ 3 ×)
        </span>
      )}
    </div>
  );
}

function BoutonExportPdf({
  campagne,
  actif,
  debut,
  fin,
  heureDebut = 0,
  heureFin = 24,
}: {
  campagne: string;
  actif: boolean;
  debut?: string;
  fin?: string;
  heureDebut?: number;
  heureFin?: number;
}) {
  return (
    <div className="mb-3 flex justify-end">
      <button
        type="button"
        disabled={!actif}
        onClick={() => telechargerPdf(campagne, debut, fin, heureDebut, heureFin)}
        className="inline-flex items-center gap-2 rounded-md bg-paa-navy-700 px-3 py-1.5
                   text-fluid-xs font-medium text-white shadow-sm transition-colors
                   hover:bg-paa-navy-900 focus:outline-none focus:ring-2 focus:ring-paa-blue-400
                   disabled:cursor-not-allowed disabled:opacity-40"
      >
        <>
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4" aria-hidden="true">
            <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" />
          </svg>
          Exporter PDF
        </>
      </button>
    </div>
  );
}

function BoutonExportCsv({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded-md border app-border px-3 py-1.5
                 text-fluid-xs font-medium app-text transition-colors
                 hover:bg-paa-blue-50 dark:hover:bg-paa-navy-800
                 focus:outline-none focus:ring-2 focus:ring-paa-blue-400"
    >
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5" aria-hidden="true">
        <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" />
      </svg>
      {label}
    </button>
  );
}

function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <th className={`px-3 py-2 text-left text-fluid-xs font-medium uppercase tracking-wide ${className ?? ""}`}>
      {children}
    </th>
  );
}

function Td({
  children,
  colSpan,
  className,
}: {
  children: React.ReactNode;
  colSpan?: number;
  className?: string;
}) {
  return (
    <td
      colSpan={colSpan}
      className={`px-3 py-2 align-top text-paa-navy-900 dark:text-paa-blue-100 ${className ?? ""}`}
    >
      {children}
    </td>
  );
}

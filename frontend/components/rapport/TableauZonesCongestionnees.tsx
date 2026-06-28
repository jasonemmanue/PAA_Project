"use client";

import { useState } from "react";

import { Card } from "@/components/ui/Card";
import type { RapportZonesCongestionnees } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8081";

/**
 * Téléchargement direct du PDF généré côté backend (fpdf2).
 * Pas de popup, pas d'aperçu — l'utilisateur reçoit directement le fichier.
 */
async function telechargerPdf(campagne: string): Promise<void> {
  const url = `${API_BASE}/rapport/zones-congestionnees/pdf?campagne=${encodeURIComponent(campagne)}`;
  try {
    const rep = await fetch(url);
    if (!rep.ok) {
      const txt = await rep.text().catch(() => "");
      throw new Error(`HTTP ${rep.status} — ${txt || rep.statusText}`);
    }
    const blob = await rep.blob();
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = `tableau16_${campagne}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  } catch (e) {
    alert("Échec de téléchargement du PDF : " + (e instanceof Error ? e.message : String(e)));
  }
}

export function TableauZonesCongestionnees({
  rapport,
}: {
  rapport: RapportZonesCongestionnees | null;
}) {
  return (
    <Card
      titre="Tableau 16 — Tronçons congestionnés (règles DEESP)"
      description={
        "Tronçon congestionné si : (a) ≥ 3 occurrences sur un jour-indicatif " +
        "à la même heure, OU (b) ≥ 4 occurrences à la même heure dans la semaine. " +
        "Critère DEESP par mesure : couleur Google Maps — rouge présent OU orange ≥ 50 % du tronçon."
      }
    >
      {/* Note seuils adaptatifs si plage < 28 jours */}
      {rapport?.regles?.adaptatif && (
        <div className="mb-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-fluid-xs text-amber-800 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
          <strong>Seuils adaptés</strong> — plage de {rapport.nb_jours_plage} jour(s)
          (référence DEESP = 28 j) : congestionné si ≥&nbsp;{rapport.regles.seuil_jour_effectif} occurrence(s) / jour
          OU ≥&nbsp;{rapport.regles.seuil_semaine_effectif} occurrence(s) / semaine.
          Élargir la plage vers 28 jours pour appliquer les seuils officiels.
        </div>
      )}

      {/* Bouton export PDF — téléchargement direct via backend fpdf2 */}
      <BoutonExportPdf campagne={rapport?.campagne ?? ""} actif={!!rapport} />


      <div className="overflow-x-auto">
        <table className="min-w-full text-fluid-sm">
          <thead className="bg-paa-navy-700 text-white dark:bg-paa-navy-800">
            <tr>
              <Th>AXE</Th>
              <Th>SOUS-TRONÇON</Th>
              <Th>TRANCHE HORAIRE</Th>
              <Th className="text-right">NB / SEMAINE</Th>
              <Th>RÈGLE DÉCLENCHÉE</Th>
              <Th>RÉPARTITION PAR JOUR</Th>
            </tr>
          </thead>
          <tbody>
            {(rapport?.entrees ?? []).map((e) => (
              <tr key={`${e.troncon_id}-${e.sous_troncon_id ?? "p"}-${e.heure}`} className="border-t app-border">
                <Td>{e.troncon_nom}</Td>
                <Td>
                  {e.sous_troncon_code ? (
                    <div className="flex flex-col">
                      <span className="font-mono font-semibold">{e.sous_troncon_code}</span>
                      <span className="text-fluid-xs app-text-muted">{e.sous_troncon_nom}</span>
                    </div>
                  ) : (
                    <span className="text-fluid-xs app-text-muted italic">axe entier</span>
                  )}
                </Td>
                <Td className="font-mono">{e.tranche}</Td>
                <Td className="text-right font-semibold">{e.nb_total_semaine}</Td>
                <Td>
                  {e.regle_jour_indicatif && (
                    <span className="mr-2 inline-block rounded bg-statut-congestionne/20 px-2 py-0.5 text-xs text-statut-congestionne">
                      ≥ 3 / jour
                    </span>
                  )}
                  {e.regle_semaine && (
                    <span className="inline-block rounded bg-amber-500/20 px-2 py-0.5 text-xs text-amber-700 dark:text-amber-300">
                      ≥ 4 / semaine
                    </span>
                  )}
                </Td>
                <Td>
                  <div className="flex flex-wrap gap-1 text-fluid-xs">
                    {Object.entries(e.nb_par_jour_semaine).map(([jour, nb]) => (
                      <span
                        key={jour}
                        className="rounded bg-paa-blue-50 px-1.5 py-0.5 dark:bg-paa-navy-800"
                      >
                        {jour}: {nb}
                      </span>
                    ))}
                  </div>
                </Td>
              </tr>
            ))}
            {(rapport?.entrees ?? []).length === 0 && (
              <tr>
                <Td colSpan={6}>
                  <span className="app-text-muted">
                    {rapport
                      ? "Aucun tronçon congestionné sur cette campagne — conforme aux observations DEESP de la zone portuaire."
                      : "Chargement…"}
                  </span>
                </Td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function BoutonExportPdf({ campagne, actif }: { campagne: string; actif: boolean }) {
  const [enCours, setEnCours] = useState(false);
  return (
    <div className="mb-3 flex justify-end">
      <button
        type="button"
        disabled={!actif || enCours}
        onClick={async () => {
          setEnCours(true);
          try { await telechargerPdf(campagne); } finally { setEnCours(false); }
        }}
        className="inline-flex items-center gap-2 rounded-md bg-paa-navy-700 px-3 py-1.5
                   text-fluid-xs font-medium text-white shadow-sm transition-colors
                   hover:bg-paa-navy-900 focus:outline-none focus:ring-2 focus:ring-paa-blue-400
                   disabled:cursor-not-allowed disabled:opacity-40"
      >
        {enCours ? (
          <>
            <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
              <path d="M22 12a10 10 0 0 1-10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
            </svg>
            Génération…
          </>
        ) : (
          <>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4" aria-hidden="true">
              <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
            Exporter PDF
          </>
        )}
      </button>
    </div>
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

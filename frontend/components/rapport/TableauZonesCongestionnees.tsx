"use client";

import { Card } from "@/components/ui/Card";
import type { RapportZonesCongestionnees } from "@/lib/types";

function exporterTableauPdf(rapport: RapportZonesCongestionnees) {
  const lignes = rapport.entrees.map((e) => {
    const sousT = e.sous_troncon_code
      ? `<div><span style="font-family:monospace;font-weight:600">${e.sous_troncon_code}</span><br><span style="font-size:9px;color:#6b7280">${e.sous_troncon_nom ?? ""}</span></div>`
      : `<em style="font-size:9px;color:#6b7280">axe entier</em>`;
    const regles = [
      e.regle_jour_indicatif ? `<span class="badge-j">≥ 3 / jour</span>` : "",
      e.regle_semaine ? `<span class="badge-s">≥ 4 / sem.</span>` : "",
    ]
      .filter(Boolean)
      .join(" ");
    const jours = Object.entries(e.nb_par_jour_semaine)
      .map(([j, n]) => `<span class="jour">${j}: ${n}</span>`)
      .join(" ");
    return `<tr>
      <td>${e.troncon_nom}</td>
      <td>${sousT}</td>
      <td style="font-family:monospace">${e.tranche}</td>
      <td style="text-align:right;font-weight:600">${e.nb_total_semaine}</td>
      <td>${regles}</td>
      <td>${jours}</td>
    </tr>`;
  });

  const html = `<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <title>Tableau 16 — Tronçons congestionnés — ${rapport.campagne}</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: Arial, Helvetica, sans-serif; font-size: 11px; padding: 20px; color: #111; }
    h2 { font-size: 13px; font-weight: 700; margin-bottom: 4px; }
    .camp { font-size: 10px; font-weight: 600; color: #1a365d; margin-bottom: 4px; }
    .desc { font-size: 9px; color: #555; margin-bottom: 14px; }
    table { border-collapse: collapse; width: 100%; }
    thead tr { background: #1a365d; color: #fff; }
    th { padding: 6px 8px; text-align: left; font-size: 9px; text-transform: uppercase; letter-spacing: .4px; }
    td { padding: 5px 8px; border-bottom: 1px solid #e5e7eb; vertical-align: top; font-size: 10px; }
    tr:nth-child(even) td { background: #f9fafb; }
    .badge-j { background: rgba(220,38,38,.12); color: #b91c1c; padding: 1px 5px; border-radius: 3px; font-size: 9px; white-space: nowrap; }
    .badge-s { background: rgba(217,119,6,.12); color: #b45309; padding: 1px 5px; border-radius: 3px; font-size: 9px; white-space: nowrap; }
    .jour { background: #eff6ff; padding: 1px 5px; border-radius: 3px; margin: 1px; white-space: nowrap; display: inline-block; }
    .vide { text-align: center; color: #6b7280; padding: 16px; font-style: italic; }
    @media print { @page { size: A4 landscape; margin: 1cm; } body { padding: 0; } }
  </style>
</head>
<body>
  <h2>Tableau 16 — Tronçons congestionnés (règles DEESP)</h2>
  <p class="camp">Campagne : ${rapport.campagne}</p>
  <p class="desc">Critère par mesure : rouge présent OU orange ≥ 50 % du tronçon.
  Congestionné si (a) ≥ 3 × sur un même jour-indicatif à la même heure,
  OU (b) ≥ 4 × à la même heure dans la semaine.</p>
  <table>
    <thead>
      <tr>
        <th>AXE</th><th>SOUS-TRONÇON</th><th>TRANCHE HORAIRE</th>
        <th style="text-align:right">NB / SEM.</th><th>RÈGLE</th><th>RÉPARTITION PAR JOUR</th>
      </tr>
    </thead>
    <tbody>
      ${
        rapport.entrees.length > 0
          ? lignes.join("\n")
          : '<tr><td colspan="6" class="vide">Aucun tronçon congestionné sur cette campagne.</td></tr>'
      }
    </tbody>
  </table>
</body>
</html>`;

  const fenetre = window.open("", "_blank", "width=1100,height=700");
  if (!fenetre) {
    alert("Autorisez les pop-ups pour exporter le PDF.");
    return;
  }
  fenetre.document.open();
  fenetre.document.write(html);
  fenetre.document.close();
  setTimeout(() => {
    fenetre.focus();
    fenetre.print();
  }, 400);
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

      {/* Bouton export PDF */}
      <div className="mb-3 flex justify-end">
        <button
          type="button"
          disabled={!rapport}
          onClick={() => rapport && exporterTableauPdf(rapport)}
          className="inline-flex items-center gap-2 rounded-md bg-paa-navy-700 px-3 py-1.5
                     text-fluid-xs font-medium text-white shadow-sm transition-colors
                     hover:bg-paa-navy-900 focus:outline-none focus:ring-2 focus:ring-paa-blue-400
                     disabled:cursor-not-allowed disabled:opacity-40"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4" aria-hidden="true">
            <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" />
          </svg>
          Exporter PDF
        </button>
      </div>

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

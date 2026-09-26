"use client";

/**
 * Barre d'actions du Rapport DEESP officiel.
 *
 * De gauche à droite, dans l'ordre de la procédure :
 *
 *   1. ⚙ Période & créneau  — définit les données applicatives retenues
 *   2. 📥 Modèle Excel      — classeur des données hors application
 *   3. 📤 Importer Excel    — dépôt du classeur complété
 *   4. 🔄 Mettre à jour     — recalcule les chiffres et les textes
 *   5. 📄 Télécharger en Word (.docx)
 *
 * Les temps de traversée, les tronçons congestionnés et les douze graphiques
 * proviennent des mesures collectées sur la période et le créneau choisis. Le
 * classeur ne porte que ce que l'application ne collecte pas : chiffres
 * macro-économiques, constats terrain, campagne de référence du tableau
 * comparatif, relevés des annexes et signataires.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import type {
  EtatParametresRapport,
  ResumeRafraichissementRapport,
} from "@/lib/types";

interface Props {
  campagne: string;
  debut: string;
  fin: string;
  heureDebut: number;
  heureFin: number;
  /** Applique une nouvelle période et un nouveau créneau au rapport. */
  onPeriodeChange: (
    debut: string,
    fin: string,
    heureDebut: number,
    heureFin: number,
  ) => void;
}

const CRENEAUX: { valeur: [number, number]; libelle: string; aide: string }[] = [
  {
    valeur: [7, 19],
    libelle: "07h – 19h",
    aide: "Plage officielle du protocole DEESP.",
  },
  {
    valeur: [0, 24],
    libelle: "24h / 24",
    aide: "Toutes les mesures, nuit comprise.",
  },
];

const LIBELLES_TENDANCE: Record<
  ResumeRafraichissementRapport["tendance_comparatif"],
  string
> = {
  baisse: "en baisse par rapport à la campagne de référence",
  hausse: "en hausse par rapport à la campagne de référence",
  contrastee: "d'évolution contrastée selon les axes",
  indeterminee: "non comparable — campagne de référence non renseignée",
};

export function BarreRapportOfficiel({
  campagne,
  debut,
  fin,
  heureDebut,
  heureFin,
  onPeriodeChange,
}: Props) {
  const { peutEcrire } = useAuth();
  const champFichier = useRef<HTMLInputElement>(null);

  const [panneauOuvert, setPanneauOuvert] = useState(false);
  const [brouillon, setBrouillon] = useState({ debut, fin, heureDebut, heureFin });
  const [etat, setEtat] = useState<EtatParametresRapport | null>(null);
  const [resume, setResume] = useState<ResumeRafraichissementRapport | null>(null);
  const [occupe, setOccupe] = useState<null | "import" | "maj" | "word">(null);
  const [message, setMessage] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    setBrouillon({ debut, fin, heureDebut, heureFin });
  }, [debut, fin, heureDebut, heureFin]);

  const chargerEtat = useCallback(async () => {
    try {
      setEtat(await api.rapportOfficielParametres(campagne));
    } catch {
      // L'état n'est qu'indicatif : son absence ne doit pas bloquer la page.
      setEtat(null);
    }
  }, [campagne]);

  useEffect(() => {
    chargerEtat();
    setResume(null);
    setMessage(null);
  }, [chargerEtat]);

  const filtre = useMemo(
    () => ({ campagne, debut, fin, heureDebut, heureFin }),
    [campagne, debut, fin, heureDebut, heureFin],
  );

  function telecharger(url: string, nom: string) {
    const lien = document.createElement("a");
    lien.href = url;
    lien.download = nom;
    document.body.appendChild(lien);
    lien.click();
    document.body.removeChild(lien);
  }

  async function importerClasseur(fichier: File) {
    setOccupe("import");
    setErreur(null);
    setMessage(null);
    try {
      const reponse = await api.rapportOfficielImporterExcel(campagne, fichier);
      const details = [
        `${reponse.nb_textes} texte(s)`,
        `${reponse.nb_valeurs_comparatif} valeur(s) de référence`,
        `${reponse.nb_lignes_annexes} ligne(s) d'annexe`,
      ].join(", ");
      setMessage(`${reponse.message} — ${details}.`);
      if (reponse.avertissements.length > 0) {
        setErreur(reponse.avertissements.join(" "));
      }
      await chargerEtat();
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setOccupe(null);
      if (champFichier.current) champFichier.current.value = "";
    }
  }

  async function mettreAJour() {
    setOccupe("maj");
    setErreur(null);
    setMessage(null);
    try {
      const reponse = await api.rapportOfficielRafraichir(filtre);
      setResume(reponse);
      setMessage(
        `Chiffres recalculés sur ${reponse.periode} (${reponse.creneau}) : ` +
          `${reponse.nb_mesures} mesure(s), ${reponse.nb_axes} axe(s), ` +
          `${reponse.nb_troncons_congestionnes} tronçon(s) congestionné(s). ` +
          `Temps moyen ${LIBELLES_TENDANCE[reponse.tendance_comparatif]}.`,
      );
      if (reponse.avertissements.length > 0) {
        setErreur(reponse.avertissements.join(" "));
      }
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setOccupe(null);
    }
  }

  async function telechargerWord() {
    setOccupe("word");
    setErreur(null);
    try {
      const reponse = await fetch(api.rapportOfficielWordUrl(filtre));
      if (!reponse.ok) {
        throw new Error(await reponse.text().catch(() => `HTTP ${reponse.status}`));
      }
      const blob = await reponse.blob();
      const url = URL.createObjectURL(blob);
      telecharger(url, `EVALUATION_DU_TEMPS_DE_TRAVERSEE_${campagne}.docx`);
      URL.revokeObjectURL(url);
      setMessage(
        "Document généré. À l'ouverture, Word recalcule la table des matières " +
          "et la pagination.",
      );
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setOccupe(null);
    }
  }

  const classeBouton =
    "inline-flex items-center gap-2 rounded-md px-3 py-2 text-fluid-sm font-semibold " +
    "transition-colors disabled:cursor-not-allowed disabled:opacity-50";

  return (
    <div className="paa-card flex flex-col gap-3 p-fluid-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-fluid-base font-bold text-paa-navy-900 dark:text-paa-blue-100">
            Rapport officiel DEESP
          </h2>
          <p className="text-fluid-xs app-text-muted">
            Reproduit le document de la DEESP à l'identique. Les temps de
            traversée proviennent des mesures de la période choisie ; le
            classeur Excel porte ce que l'application ne collecte pas.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* 1 — Période & créneau retenus pour les données de l'application */}
          <button
            type="button"
            onClick={() => setPanneauOuvert((ouvert) => !ouvert)}
            className={`${classeBouton} border app-border app-surface text-paa-navy-800 dark:text-paa-blue-100 hover:bg-paa-navy-50 dark:hover:bg-paa-navy-800`}
            aria-expanded={panneauOuvert}
          >
            ⚙ Période & créneau
            <span className="rounded bg-paa-navy-700 px-1.5 py-0.5 text-[11px] font-bold text-white">
              {heureDebut === 0 && heureFin >= 24
                ? "24h/24"
                : `${String(heureDebut).padStart(2, "0")}h–${String(heureFin).padStart(2, "0")}h`}
            </span>
          </button>

          {/* 2 — Classeur des données hors application */}
          <button
            type="button"
            onClick={() =>
              telecharger(
                api.rapportOfficielModeleExcelUrl(campagne),
                `rapport_deesp_donnees_${campagne}.xlsx`,
              )
            }
            className={`${classeBouton} border app-border app-surface text-paa-navy-800 dark:text-paa-blue-100 hover:bg-paa-navy-50 dark:hover:bg-paa-navy-800`}
            title="Télécharge le classeur pré-rempli à compléter"
          >
            📥 Modèle Excel
          </button>

          {/* 3 — Dépôt du classeur complété */}
          {peutEcrire && (
            <>
              <input
                ref={champFichier}
                type="file"
                accept=".xlsx,.xlsm"
                className="hidden"
                onChange={(e) => {
                  const fichier = e.target.files?.[0];
                  if (fichier) importerClasseur(fichier);
                }}
              />
              <button
                type="button"
                onClick={() => champFichier.current?.click()}
                disabled={occupe !== null}
                className={`${classeBouton} border app-border app-surface text-paa-navy-800 dark:text-paa-blue-100 hover:bg-paa-navy-50 dark:hover:bg-paa-navy-800`}
                title="Dépose le classeur complété"
              >
                {occupe === "import" ? "Import en cours…" : "📤 Importer Excel"}
              </button>
            </>
          )}

          {/* 4 — Recalcul des chiffres et des textes */}
          <button
            type="button"
            onClick={mettreAJour}
            disabled={occupe !== null}
            className={`${classeBouton} bg-paa-navy-700 text-white hover:bg-paa-navy-800`}
            title="Recalcule les chiffres et les textes du rapport"
          >
            {occupe === "maj" ? "Mise à jour…" : "🔄 Mettre à jour"}
          </button>

          {/* 5 — Document final */}
          <button
            type="button"
            onClick={telechargerWord}
            disabled={occupe !== null}
            className={`${classeBouton} bg-paa-blue-500 text-white shadow-paa-sm hover:bg-paa-blue-400`}
          >
            {occupe === "word"
              ? "Génération du document…"
              : "📄 Télécharger en Word (.docx)"}
          </button>
        </div>
      </div>

      {panneauOuvert && (
        <div className="flex flex-col gap-3 rounded-md border app-border bg-paa-navy-50/60 p-3 dark:bg-paa-navy-900/40">
          <p className="text-fluid-xs app-text-muted">
            Sélectionne les mesures reprises dans le rapport : seules celles
            collectées dans cette période et ce créneau alimentent les tableaux
            et les graphiques.
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-fluid-xs font-medium app-text-muted">
                Début des données
              </span>
              <input
                type="date"
                value={brouillon.debut}
                max={brouillon.fin}
                onChange={(e) =>
                  setBrouillon((b) => ({ ...b, debut: e.target.value }))
                }
                className="min-h-[40px] rounded-md border app-border app-surface px-3 py-2 text-fluid-sm text-paa-navy-900 dark:text-paa-blue-100"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-fluid-xs font-medium app-text-muted">
                Fin des données
              </span>
              <input
                type="date"
                value={brouillon.fin}
                min={brouillon.debut}
                onChange={(e) =>
                  setBrouillon((b) => ({ ...b, fin: e.target.value }))
                }
                className="min-h-[40px] rounded-md border app-border app-surface px-3 py-2 text-fluid-sm text-paa-navy-900 dark:text-paa-blue-100"
              />
            </label>
            <fieldset className="flex flex-col gap-1">
              <legend className="text-fluid-xs font-medium app-text-muted">
                Créneau horaire
              </legend>
              <div className="flex gap-2">
                {CRENEAUX.map((creneau) => {
                  const actif =
                    brouillon.heureDebut === creneau.valeur[0] &&
                    brouillon.heureFin === creneau.valeur[1];
                  return (
                    <button
                      key={creneau.libelle}
                      type="button"
                      title={creneau.aide}
                      onClick={() =>
                        setBrouillon((b) => ({
                          ...b,
                          heureDebut: creneau.valeur[0],
                          heureFin: creneau.valeur[1],
                        }))
                      }
                      className={`min-h-[40px] rounded-md border px-3 py-2 text-fluid-sm font-semibold transition-colors ${
                        actif
                          ? "border-paa-navy-700 bg-paa-navy-700 text-white"
                          : "app-border app-surface text-paa-navy-800 dark:text-paa-blue-100"
                      }`}
                    >
                      {creneau.libelle}
                    </button>
                  );
                })}
              </div>
            </fieldset>
            <button
              type="button"
              onClick={() => {
                onPeriodeChange(
                  brouillon.debut,
                  brouillon.fin,
                  brouillon.heureDebut,
                  brouillon.heureFin,
                );
                setPanneauOuvert(false);
              }}
              className={`${classeBouton} bg-paa-navy-700 text-white hover:bg-paa-navy-800`}
            >
              ✓ Appliquer
            </button>
          </div>
        </div>
      )}

      {etat && (
        <p className="text-fluid-xs app-text-muted">
          {etat.importe
            ? `Classeur importé pour ${campagne} : ${etat.nb_textes} texte(s), ` +
              `${etat.nb_valeurs_comparatif} valeur(s) de référence, ` +
              `${etat.nb_donnees_directes} surcharge(s), ` +
              `${etat.nb_lignes_annexes} ligne(s) d'annexe.`
            : `Aucun classeur importé pour ${campagne} : les textes de référence ` +
              "seront utilisés et les annexes resteront vides."}
        </p>
      )}

      {message && (
        <div className="rounded-md border border-statut-fluide/40 bg-statut-fluide/10 px-3 py-2 text-fluid-xs text-statut-fluide">
          {message}
        </div>
      )}

      {erreur && (
        <div className="rounded-md border border-amber-400/60 bg-amber-400/10 px-3 py-2 text-fluid-xs text-amber-700 dark:text-amber-300">
          {erreur}
        </div>
      )}

      {resume && Object.keys(resume.temps_moyen_par_sens).length > 0 && (
        <details className="rounded-md border app-border px-3 py-2">
          <summary className="cursor-pointer text-fluid-xs font-semibold text-paa-navy-800 dark:text-paa-blue-100">
            Temps moyen retenu par sens de circulation
          </summary>
          <ul className="mt-2 flex flex-col gap-1">
            {Object.entries(resume.temps_moyen_par_sens).map(([sens, valeurs]) => (
              <li key={sens} className="text-fluid-xs app-text-muted">
                <span className="font-medium">{sens}</span> —{" "}
                jours ouvrables : {valeurs.jour_ouvrable ?? "—"} Mn, week-ends :{" "}
                {valeurs.week_end ?? "—"} Mn
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

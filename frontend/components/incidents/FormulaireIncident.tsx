"use client";

/**
 * Saisie et correction manuelle d'un incident.
 *
 * Le scraping de la presse alimente la table automatiquement, mais un agent
 * du port doit pouvoir enregistrer un incident constaté sur le terrain avant
 * toute reprise médiatique, et corriger une classification automatique
 * erronée (type, sévérité, lieu, tronçon rattaché).
 */

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { Incident, IncidentSaisie, SeveriteIncident, Troncon } from "@/lib/types";

import type { TypeIncidentApi } from "./FiltresIncidents";

interface Props {
  /** Incident à corriger, ou `null` pour une création. */
  incident: Incident | null;
  types: TypeIncidentApi[];
  troncons: Troncon[];
  onFerme: () => void;
  /** Appelé après un enregistrement réussi, pour rafraîchir la liste. */
  onEnregistre: () => void;
}

const SEVERITES: { valeur: SeveriteIncident; libelle: string }[] = [
  { valeur: "mineur", libelle: "Mineur" },
  { valeur: "moyen", libelle: "Modéré" },
  { valeur: "grave", libelle: "Grave" },
  { valeur: "inconnu", libelle: "Inconnu" },
];

/** Convertit un horodatage ISO en valeur d'input datetime-local. */
function versChampLocal(iso: string | null | undefined): string {
  const date = iso ? new Date(iso) : new Date();
  const decalage = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - decalage).toISOString().slice(0, 16);
}

export function FormulaireIncident({
  incident,
  types,
  troncons,
  onFerme,
  onEnregistre,
}: Props) {
  const creation = incident === null;

  const [titre, setTitre] = useState(incident?.titre ?? "");
  const [resume, setResume] = useState(incident?.resume ?? "");
  const [sourceUrl, setSourceUrl] = useState(
    // Une référence interne générée par le serveur n'a pas à être rééditée.
    incident?.source_url?.startsWith("interne://") ? "" : incident?.source_url ?? "",
  );
  const [sourceNom, setSourceNom] = useState(incident?.source_nom ?? "saisie_manuelle");
  const [horodatage, setHorodatage] = useState(
    versChampLocal(incident?.horodatage_publication),
  );
  const [lieu, setLieu] = useState(incident?.lieu_extrait ?? "");
  const [lat, setLat] = useState(incident?.lat?.toString() ?? "");
  const [lon, setLon] = useState(incident?.lon?.toString() ?? "");
  const [tronconId, setTronconId] = useState(incident?.troncon_id?.toString() ?? "");
  const [type, setType] = useState(incident?.type_incident ?? "");
  const [severite, setSeverite] = useState<string>(incident?.severite ?? "inconnu");
  const [verifie, setVerifie] = useState(incident?.verifie ?? false);

  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  // Fermeture au clavier — le formulaire est modal.
  useEffect(() => {
    function surTouche(evenement: KeyboardEvent) {
      if (evenement.key === "Escape") onFerme();
    }
    window.addEventListener("keydown", surTouche);
    return () => window.removeEventListener("keydown", surTouche);
  }, [onFerme]);

  function nombreOuNull(valeur: string): number | null {
    const trim = valeur.trim();
    if (!trim) return null;
    const nombre = Number(trim.replace(",", "."));
    return Number.isFinite(nombre) ? nombre : null;
  }

  async function enregistrer() {
    if (titre.trim().length < 3) {
      setErreur("Le titre doit comporter au moins 3 caractères.");
      return;
    }
    setEnCours(true);
    setErreur(null);

    const payload: IncidentSaisie = {
      titre: titre.trim(),
      resume: resume.trim() || null,
      source_url: sourceUrl.trim() || null,
      source_nom: sourceNom.trim() || "saisie_manuelle",
      horodatage_publication: new Date(horodatage).toISOString(),
      lieu_extrait: lieu.trim() || null,
      lat: nombreOuNull(lat),
      lon: nombreOuNull(lon),
      troncon_id: tronconId ? Number(tronconId) : null,
      type_incident: type || null,
      severite: (severite || null) as SeveriteIncident | null,
      verifie,
    };

    try {
      if (creation) {
        await api.creerIncident(payload);
      } else {
        await api.majIncident(incident.id, payload);
      }
      onEnregistre();
      onFerme();
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setEnCours(false);
    }
  }

  const classeChamp =
    "w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white " +
    "dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 " +
    "focus:outline-none focus:ring-2 focus:ring-paa-blue-400";
  const classeLibelle =
    "block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1";

  return (
    <div
      className="fixed inset-0 z-[1300] flex items-center justify-center bg-black/40 p-4"
      onClick={onFerme}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white p-6 shadow-2xl dark:bg-gray-800"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">
              {creation ? "Nouvel incident" : "Corriger l’incident"}
            </h3>
            <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
              {creation
                ? "Constat terrain ou signalement hors presse."
                : "Les corrections remplacent la classification automatique."}
            </p>
          </div>
          <button
            type="button"
            onClick={onFerme}
            className="shrink-0 text-xl leading-none text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            aria-label="Fermer"
          >
            ×
          </button>
        </div>

        <div className="flex flex-col gap-3">
          <div>
            <label className={classeLibelle} htmlFor="incident-titre">
              Titre *
            </label>
            <input
              id="incident-titre"
              className={classeChamp}
              value={titre}
              onChange={(e) => setTitre(e.target.value)}
              placeholder="Camion renversé sur le boulevard du Port"
            />
          </div>

          <div>
            <label className={classeLibelle} htmlFor="incident-resume">
              Résumé
            </label>
            <textarea
              id="incident-resume"
              className={`${classeChamp} min-h-[80px]`}
              value={resume}
              onChange={(e) => setResume(e.target.value)}
              placeholder="Circonstances, voies impactées, durée estimée…"
            />
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className={classeLibelle} htmlFor="incident-type">
                Type
              </label>
              <select
                id="incident-type"
                className={classeChamp}
                value={type}
                onChange={(e) => setType(e.target.value)}
              >
                <option value="">— Non classé —</option>
                {types
                  .filter((tp) => tp.actif)
                  .map((tp) => (
                    <option key={tp.slug} value={tp.slug}>
                      {tp.libelle}
                    </option>
                  ))}
              </select>
            </div>
            <div>
              <label className={classeLibelle} htmlFor="incident-severite">
                Sévérité
              </label>
              <select
                id="incident-severite"
                className={classeChamp}
                value={severite}
                onChange={(e) => setSeverite(e.target.value)}
              >
                {SEVERITES.map((s) => (
                  <option key={s.valeur} value={s.valeur}>
                    {s.libelle}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className={classeLibelle} htmlFor="incident-date">
                Date et heure de l’incident
              </label>
              <input
                id="incident-date"
                type="datetime-local"
                className={classeChamp}
                value={horodatage}
                onChange={(e) => setHorodatage(e.target.value)}
              />
            </div>
            <div>
              <label className={classeLibelle} htmlFor="incident-troncon">
                Tronçon impacté
              </label>
              <select
                id="incident-troncon"
                className={classeChamp}
                value={tronconId}
                onChange={(e) => setTronconId(e.target.value)}
              >
                <option value="">— Aucun —</option>
                {troncons.map((tr) => (
                  <option key={tr.id} value={tr.id}>
                    {tr.nom}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className={classeLibelle} htmlFor="incident-lieu">
              Lieu
            </label>
            <input
              id="incident-lieu"
              className={classeChamp}
              value={lieu}
              onChange={(e) => setLieu(e.target.value)}
              placeholder="Carrefour Seamen’s Club"
            />
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className={classeLibelle} htmlFor="incident-lat">
                Latitude
              </label>
              <input
                id="incident-lat"
                className={classeChamp}
                value={lat}
                onChange={(e) => setLat(e.target.value)}
                placeholder="5.293656"
              />
            </div>
            <div>
              <label className={classeLibelle} htmlFor="incident-lon">
                Longitude
              </label>
              <input
                id="incident-lon"
                className={classeChamp}
                value={lon}
                onChange={(e) => setLon(e.target.value)}
                placeholder="-4.008266"
              />
            </div>
          </div>
          <p className="-mt-1 text-xs text-gray-500 dark:text-gray-400">
            Sans coordonnées, l’incident n’apparaîtra pas sur les cartes.
          </p>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className={classeLibelle} htmlFor="incident-source-nom">
                Source
              </label>
              <input
                id="incident-source-nom"
                className={classeChamp}
                value={sourceNom}
                onChange={(e) => setSourceNom(e.target.value)}
              />
            </div>
            <div>
              <label className={classeLibelle} htmlFor="incident-source-url">
                Lien de l’article
              </label>
              <input
                id="incident-source-url"
                className={classeChamp}
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
                placeholder="Laissez vide pour un constat terrain"
              />
            </div>
          </div>

          <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
            <input
              type="checkbox"
              checked={verifie}
              onChange={(e) => setVerifie(e.target.checked)}
              className="h-4 w-4"
            />
            Incident vérifié sur le terrain
          </label>

          {erreur && (
            <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-700 dark:bg-red-900/30 dark:text-red-300">
              {erreur}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onFerme}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700"
            >
              Annuler
            </button>
            <button
              type="button"
              onClick={enregistrer}
              disabled={enCours}
              className="rounded-md bg-paa-navy-700 px-4 py-2 text-sm font-semibold text-white hover:bg-paa-navy-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {enCours ? "Enregistrement…" : creation ? "Créer" : "Enregistrer"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

"use client";

/**
 * Onglet "Axes principaux" — création/archivage des axes officiels et de
 * tout nouveau tronçon (ex. AGL → Grand Moulin).
 *
 * Un tronçon créé ici est immédiatement adopté par toutes les chaînes du
 * projet, sans redéploiement ni redémarrage (cf. CLAUDE.md § 4.6) :
 *  - collecte Google au prochain cycle,
 *  - carte temps réel + état /carte/etat,
 *  - indicateurs FHWA + heatmap horaire,
 *  - profils horaires nocturnes,
 *  - temps de traversée par période (page Prédiction),
 *  - rapport DEESP (Tableaux 3-17, 19 + Graphiques 1-12),
 *  - calibration GPX terrain.
 */

import dynamic from "next/dynamic";
import { useState } from "react";

import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { TronconAdmin } from "@/lib/types";

const CarteAdmin = dynamic(
  () => import("@/components/administration/CarteAdmin").then((m) => m.CarteAdmin),
  { ssr: false },
);

export function OngletAxes({
  troncons,
  onChange,
}: {
  troncons: TronconAdmin[];
  onChange: () => void;
}) {
  const [nom, setNom] = useState<string>("");
  const [debut, setDebut] = useState<{ lat: number; lon: number } | null>(null);
  const [fin, setFin] = useState<{ lat: number; lon: number } | null>(null);
  const [pointActif, setPointActif] = useState<"debut" | "fin" | null>(null);
  const [couleur, setCouleur] = useState<string>("#9C27B0");
  const [estAxe, setEstAxe] = useState<boolean>(false); // par défaut tronçon supplémentaire
  const [erreur, setErreur] = useState<string | null>(null);
  const [succes, setSucces] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  const reinitialiser = () => {
    setNom("");
    setDebut(null);
    setFin(null);
    setPointActif(null);
    setErreur(null);
  };

  const handleClickCarte = (lat: number, lon: number) => {
    if (pointActif === "debut") {
      setDebut({ lat, lon });
      setPointActif("fin");
    } else if (pointActif === "fin") {
      setFin({ lat, lon });
      setPointActif(null);
    }
  };

  const valider = async () => {
    if (!nom.trim() || !debut || !fin) {
      setErreur("Renseigne le nom + place les 2 markers (Début, Fin).");
      return;
    }
    setEnCours(true);
    setErreur(null);
    setSucces(null);
    try {
      const t = await api.creerTroncon({
        nom: nom.trim(),
        lat_origine: debut.lat,
        lon_origine: debut.lon,
        lat_destination: fin.lat,
        lon_destination: fin.lon,
        couleur,
        est_axe: estAxe,
      });
      const ad = t.adoption_collecte;
      const lignes = [
        `✅ Tronçon créé : ${t.nom} (id=${t.id}, ${t.distance_km} km)`,
        "Il est automatiquement inclus au prochain cycle de collecte Google et dans toutes les analyses (carte, indicateurs, profils horaires, temps de traversée par période, rapport, calibration GPX).",
      ];
      if (ad) {
        lignes.push(
          `Surveillance : ${ad.nb_troncons_actifs} tronçons actifs · ` +
            `Google estimé ${ad.google_requetes_par_jour}/${ad.plafond_google} req/jour.`,
        );
        if (ad.avertissement_quota) lignes.push(`⚠ ${ad.avertissement_quota}`);
      }
      setSucces(lignes.join("\n"));
      reinitialiser();
      onChange();
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setEnCours(false);
    }
  };

  const archiver = async (t: TronconAdmin) => {
    if (!confirm(`Archiver "${t.nom}" ? L'historique est conservé.`)) return;
    try {
      await api.supprimerTroncon(t.id);
      onChange();
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="flex flex-col gap-fluid-4">
      {/* Formulaire de création */}
      <Card
        titre="Créer un nouvel axe"
        description="Donnez un nom au tronçon, puis placez les markers Début et Fin en cliquant sur la carte (ou en saisissant les coordonnées)."
      >
        <div className="flex flex-col gap-3">
          {/* Nom */}
          <label className="flex flex-col gap-1 text-fluid-sm font-medium">
            Nom du tronçon
            <input
              type="text"
              value={nom}
              onChange={(e) => setNom(e.target.value)}
              placeholder="ex. AGL → Grand Moulin"
              className="rounded-md border app-border app-surface px-3 py-2 text-fluid-base
                         focus:outline-none focus:ring-2 focus:ring-paa-blue-400 min-h-[42px]"
            />
          </label>

          {/* Coords manuelles */}
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-md border app-border p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-fluid-xs font-medium app-text-muted">
                  🟢 Point DÉBUT
                </span>
                <button
                  type="button"
                  onClick={() =>
                    setPointActif(pointActif === "debut" ? null : "debut")
                  }
                  className={
                    "text-fluid-xs font-medium px-2 py-1 rounded " +
                    (pointActif === "debut"
                      ? "bg-paa-navy-700 text-white"
                      : "bg-paa-blue-50 text-paa-navy-700 hover:bg-paa-blue-100 dark:bg-paa-navy-800 dark:text-paa-blue-100")
                  }
                >
                  📍 Placer
                </button>
              </div>
              {debut ? (
                <div className="font-mono text-fluid-xs">
                  lat: {debut.lat.toFixed(6)}<br />lon: {debut.lon.toFixed(6)}
                </div>
              ) : (
                <p className="text-fluid-xs app-text-muted">
                  Cliquez « Placer » puis sur la carte
                </p>
              )}
            </div>
            <div className="rounded-md border app-border p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-fluid-xs font-medium app-text-muted">
                  🔴 Point FIN
                </span>
                <button
                  type="button"
                  onClick={() =>
                    setPointActif(pointActif === "fin" ? null : "fin")
                  }
                  className={
                    "text-fluid-xs font-medium px-2 py-1 rounded " +
                    (pointActif === "fin"
                      ? "bg-paa-navy-700 text-white"
                      : "bg-paa-blue-50 text-paa-navy-700 hover:bg-paa-blue-100 dark:bg-paa-navy-800 dark:text-paa-blue-100")
                  }
                >
                  📍 Placer
                </button>
              </div>
              {fin ? (
                <div className="font-mono text-fluid-xs">
                  lat: {fin.lat.toFixed(6)}<br />lon: {fin.lon.toFixed(6)}
                </div>
              ) : (
                <p className="text-fluid-xs app-text-muted">
                  Cliquez « Placer » puis sur la carte
                </p>
              )}
            </div>
          </div>

          {/* Catégorie axe / tronçon */}
          <fieldset className="rounded-md border app-border p-3">
            <legend className="px-2 text-fluid-xs font-semibold app-text-muted uppercase tracking-wide">
              Catégorie
            </legend>
            <div className="flex flex-wrap gap-3">
              <label className="flex cursor-pointer items-center gap-2 text-fluid-sm">
                <input type="radio" name="cat" checked={!estAxe}
                       onChange={() => setEstAxe(false)} className="accent-paa-blue-600" />
                <span><strong>Tronçon</strong> — sous-portion du réseau (défaut)</span>
              </label>
              <label className="flex cursor-pointer items-center gap-2 text-fluid-sm">
                <input type="radio" name="cat" checked={estAxe}
                       onChange={() => setEstAxe(true)} className="accent-paa-blue-600" />
                <span><strong>Axe</strong> — axe officiel DEESP (mêmes propriétés que les 6 axes initiaux)</span>
              </label>
            </div>
          </fieldset>

          {/* Couleur + bouton */}
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1 text-fluid-sm font-medium">
              Couleur affichage
              <input
                type="color"
                value={couleur}
                onChange={(e) => setCouleur(e.target.value)}
                className="h-10 w-20 rounded border app-border cursor-pointer"
              />
            </label>
            <button
              type="button"
              onClick={valider}
              disabled={enCours || !nom.trim() || !debut || !fin}
              className="btn-primary disabled:opacity-50 min-h-[42px]"
            >
              {enCours ? "Création…" : "✅ Créer le tronçon"}
            </button>
            <button
              type="button"
              onClick={reinitialiser}
              className="btn-secondary min-h-[42px]"
            >
              ↺ Réinitialiser
            </button>
          </div>

          {erreur && (
            <div className="rounded-md bg-statut-congestionne/10 border border-statut-congestionne/40 px-3 py-2 text-fluid-sm text-statut-congestionne">
              {erreur}
            </div>
          )}
          {succes && (
            <div className="whitespace-pre-line rounded-md bg-statut-fluide/10 border border-statut-fluide/40 px-3 py-2 text-fluid-sm text-statut-fluide">
              {succes}
            </div>
          )}
        </div>
      </Card>

      {/* Carte */}
      <Card
        titre="Carte interactive"
        description={
          `Les ${troncons.filter((t) => t.actif).length} tronçons actifs en pointillés. Le nouveau tronçon en violet plein.`
        }
      >
        <CarteAdmin
          pointActif={pointActif}
          debut={debut}
          fin={fin}
          polylinesParent={troncons
            .filter((t) => t.actif && t.polyline)
            .map((t) => ({ id: t.id, polyline: t.polyline, couleur: t.couleur }))}
          onClick={handleClickCarte}
        />
      </Card>

      {/* Liste des axes et tronçons existants
          Fallback : si la migration 0013 n'est pas appliquée (est_axe undefined),
          on considère que les IDs 1-6 sont les axes officiels du seed initial. */}
      <Card titre={(() => {
        const actifs = troncons.filter((t) => t.actif);
        const estAxeReel = (t: { id: number; est_axe?: boolean }) => t.est_axe ?? (t.id <= 6);
        const nAxes = actifs.filter(estAxeReel).length;
        const nTr = actifs.length - nAxes;
        return `${nAxes} axe${nAxes > 1 ? "s" : ""} actif${nAxes > 1 ? "s" : ""}${nTr > 0 ? ` + ${nTr} tronçon${nTr > 1 ? "s" : ""}` : ""}`;
      })()}>
        <div className="overflow-x-auto">
          <table className="min-w-full text-fluid-sm">
            <thead className="bg-paa-blue-50 dark:bg-paa-navy-800">
              <tr className="text-left">
                <th className="px-3 py-2 font-medium">ID</th>
                <th className="px-3 py-2 font-medium">Catégorie</th>
                <th className="px-3 py-2 font-medium">Nom</th>
                <th className="px-3 py-2 font-medium text-right">Distance</th>
                <th className="px-3 py-2 font-medium">Couleur</th>
                <th className="px-3 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {troncons.map((t) => (
                <tr
                  key={t.id}
                  className={
                    "border-t app-border " + (t.actif ? "" : "opacity-50")
                  }
                >
                  <td className="px-3 py-2 font-mono">{t.id}</td>
                  <td className="px-3 py-2">
                    {(t.est_axe ?? (t.id <= 6)) ? (
                      <span className="inline-block rounded bg-paa-navy-700 px-2 py-0.5 text-fluid-xs font-semibold text-white">
                        AXE
                      </span>
                    ) : (
                      <span className="inline-block rounded bg-paa-blue-50 px-2 py-0.5 text-fluid-xs font-semibold text-paa-navy-800 dark:bg-paa-navy-800 dark:text-paa-blue-100">
                        Tronçon
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2">{t.nom}</td>
                  <td className="px-3 py-2 text-right">{t.distance_km} km</td>
                  <td className="px-3 py-2">
                    <span
                      className="inline-block h-4 w-4 rounded border app-border align-middle"
                      style={{ backgroundColor: t.couleur }}
                    />{" "}
                    <span className="font-mono text-fluid-xs app-text-muted">
                      {t.couleur}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    {t.actif ? (
                      <button
                        type="button"
                        onClick={() => archiver(t)}
                        className="text-fluid-xs text-statut-congestionne hover:underline"
                      >
                        🗄 Archiver
                      </button>
                    ) : (
                      <span className="text-fluid-xs app-text-muted">
                        Archivé
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

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
import { useEffect, useState } from "react";

import { AutocompleteLieu } from "@/components/administration/AutocompleteLieu";
import { Card } from "@/components/ui/Card";
import { useAuth } from "@/contexts/AuthContext";
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
  const { peutEcrire } = useAuth();
  const [nom, setNom] = useState<string>("");
  const [debut, setDebut] = useState<{ lat: number; lon: number } | null>(null);
  const [fin, setFin] = useState<{ lat: number; lon: number } | null>(null);
  const [pointActif, setPointActif] = useState<"debut" | "fin" | null>(null);
  const [couleur, setCouleur] = useState<string>("#9C27B0");
  const [estAxe] = useState<boolean>(true);
  const [erreur, setErreur] = useState<string | null>(null);
  const [succes, setSucces] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  // Mode avancé (repli sur clic-carte + saisie manuelle des coords)
  const [modeAvance, setModeAvance] = useState<boolean>(false);

  // Prévisualisation OSRM du tracé routier (auto-fetch dès qu'on a les 2 points)
  const [previewPolyline, setPreviewPolyline] = useState<string | null>(null);
  const [previewSource, setPreviewSource] = useState<"osrm" | "haversine" | null>(null);
  const [previewKm, setPreviewKm] = useState<number | null>(null);
  const [previewChargement, setPreviewChargement] = useState<boolean>(false);

  useEffect(() => {
    setPreviewPolyline(null);
    setPreviewSource(null);
    setPreviewKm(null);
    if (!debut || !fin) return;
    let annule = false;
    setPreviewChargement(true);
    const timer = window.setTimeout(async () => {
      try {
        const r = await api.previewRoute(debut.lat, debut.lon, fin.lat, fin.lon);
        if (annule) return;
        setPreviewPolyline(r.polyline);
        setPreviewSource(r.source);
        setPreviewKm(r.distance_km);
      } catch {
        if (!annule) {
          setPreviewPolyline(null);
          setPreviewSource(null);
        }
      } finally {
        if (!annule) setPreviewChargement(false);
      }
    }, 350);
    return () => {
      annule = true;
      window.clearTimeout(timer);
    };
  }, [debut, fin]);

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
        `✅ Axe créé : ${t.nom} (id=${t.id}, ${t.distance_km} km)`,
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

  // --- Édition inline d'un axe existant ---
  const [editId, setEditId] = useState<number | null>(null);
  const [editNom, setEditNom] = useState<string>("");
  const [editCouleur, setEditCouleur] = useState<string>("#000000");
  const [editVitesse, setEditVitesse] = useState<number>(50);
  const [editLatOrig, setEditLatOrig] = useState<string>("");
  const [editLonOrig, setEditLonOrig] = useState<string>("");
  const [editLatDest, setEditLatDest] = useState<string>("");
  const [editLonDest, setEditLonDest] = useState<string>("");
  const [editErreur, setEditErreur] = useState<string | null>(null);
  const [editEnCours, setEditEnCours] = useState<boolean>(false);

  const ouvrirEdition = (t: TronconAdmin) => {
    setEditId(t.id);
    setEditNom(t.nom);
    setEditCouleur(t.couleur ?? "#000000");
    setEditVitesse(t.vitesse_ref_kmh ?? 50);
    setEditLatOrig(t.lat_origine != null ? String(t.lat_origine) : "");
    setEditLonOrig(t.lon_origine != null ? String(t.lon_origine) : "");
    setEditLatDest(t.lat_destination != null ? String(t.lat_destination) : "");
    setEditLonDest(t.lon_destination != null ? String(t.lon_destination) : "");
    setEditErreur(null);
  };

  const annulerEdition = () => setEditId(null);

  const enregistrerEdition = async () => {
    if (editId === null) return;
    setEditEnCours(true);
    setEditErreur(null);
    try {
      const payload: Parameters<typeof api.majTroncon>[1] = {
        nom: editNom.trim(),
        couleur: editCouleur,
        vitesse_ref_kmh: editVitesse,
      };
      const parseNum = (s: string) => (s.trim() === "" ? undefined : Number(s));
      const lo = parseNum(editLatOrig);
      const lg = parseNum(editLonOrig);
      const ld = parseNum(editLatDest);
      const lgd = parseNum(editLonDest);
      if (lo !== undefined) payload.lat_origine = lo;
      if (lg !== undefined) payload.lon_origine = lg;
      if (ld !== undefined) payload.lat_destination = ld;
      if (lgd !== undefined) payload.lon_destination = lgd;
      await api.majTroncon(editId, payload);
      setEditId(null);
      onChange();
    } catch (e) {
      setEditErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setEditEnCours(false);
    }
  };

  return (
    <div className="flex flex-col gap-fluid-4">
      {/* Formulaire de création + carte interactive — masqués en mode lecture */}
      {peutEcrire && (
      <><Card
        titre="Créer un nouvel axe"
        description="Saisissez le nom des endroits de départ et d'arrivée : l'application propose des suggestions OpenStreetMap et remplit automatiquement les coordonnées GPS."
      >
        <div className="flex flex-col gap-3">
          {/* Nom */}
          <label className="flex flex-col gap-1 text-fluid-sm font-medium">
            Nom de l&apos;axe
            <input
              type="text"
              value={nom}
              onChange={(e) => setNom(e.target.value)}
              placeholder="ex. AGL → Grand Moulin"
              className="rounded-md border app-border app-surface px-3 py-2 text-fluid-base
                         focus:outline-none focus:ring-2 focus:ring-paa-blue-400 min-h-[42px]"
            />
          </label>

          {/* Autocomplétion des lieux (nouveau) */}
          <div className="rounded-lg border app-border bg-paa-blue-50/40 dark:bg-paa-navy-800/40 p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-fluid-sm font-semibold text-paa-navy-700 dark:text-paa-blue-200">
                📍 Saisie par nom d&apos;endroit (recommandé)
              </h3>
              <button
                type="button"
                onClick={() => setModeAvance((v) => !v)}
                className="text-fluid-xs text-paa-navy-700 dark:text-paa-blue-200 hover:underline"
              >
                {modeAvance ? "▲ Masquer le mode avancé" : "▼ Mode avancé (clic carte)"}
              </button>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <AutocompleteLieu
                label="Point de début"
                couleurBadge="#16a34a"
                placeholder="ex. CARENA, Plateau, Abidjan"
                onSelect={(_nom, lat, lon) => setDebut({ lat, lon })}
                onEffacer={() => setDebut(null)}
              />
              <AutocompleteLieu
                label="Point de fin"
                couleurBadge="#dc2626"
                placeholder="ex. Pharmacie Palm Beach"
                onSelect={(_nom, lat, lon) => setFin({ lat, lon })}
                onEffacer={() => setFin(null)}
              />
            </div>
            {(debut || fin) && (
              <div className="mt-3 grid gap-2 md:grid-cols-2 text-fluid-xs">
                {debut && (
                  <div className="rounded bg-white dark:bg-paa-navy-900 border app-border px-3 py-2 font-mono">
                    🟢 Début : lat {debut.lat.toFixed(6)}, lon {debut.lon.toFixed(6)}
                  </div>
                )}
                {fin && (
                  <div className="rounded bg-white dark:bg-paa-navy-900 border app-border px-3 py-2 font-mono">
                    🔴 Fin : lat {fin.lat.toFixed(6)}, lon {fin.lon.toFixed(6)}
                  </div>
                )}
              </div>
            )}
            <p className="mt-2 text-fluid-xs app-text-muted">
              Vous pouvez aussi demander les coordonnées d&apos;un lieu au chatbot en bas à droite (bouton « Aide »).
            </p>
          </div>

          {/* Mode avancé — clic carte + saisie manuelle */}
          {modeAvance && (
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-md border app-border p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-fluid-xs font-medium app-text-muted">
                  🟢 Point DÉBUT (clic carte)
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
                  🔴 Point FIN (clic carte)
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
          )}

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
              {enCours ? "Création…" : "✅ Créer l'axe"}
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

      {/* Carte — toujours visible pour voir l'aperçu du tracé, quelle
          que soit la méthode de saisie (autocomplete ou clic-carte) */}
      <Card
        titre="Aperçu du tracé sur la carte"
        description={
          debut && fin
            ? previewChargement
              ? "Calcul du tracé routier en cours…"
              : previewSource === "osrm"
                ? `Tracé routier OSRM (${previewKm?.toFixed(2)} km). Il sera le tracé définitif après création.`
                : previewSource === "haversine"
                  ? `Aperçu linéaire (${previewKm?.toFixed(2)} km à vol d'oiseau) — OSRM indisponible, le tracé final sera calculé côté serveur.`
                  : "Aperçu linéaire — placez début + fin pour voir le tracé routier calculé."
            : `Les ${troncons.filter((t) => t.actif).length} axes actifs en pointillés. Placez début + fin pour voir l'aperçu.`
        }
      >
        <CarteAdmin
          pointActif={pointActif}
          debut={debut}
          fin={fin}
          previewPolyline={previewPolyline}
          previewSource={previewSource}
          polylinesParent={troncons
            .filter((t) => t.actif && t.polyline)
            .map((t) => ({ id: t.id, polyline: t.polyline, couleur: t.couleur }))}
          onClick={handleClickCarte}
        />
      </Card>
      </>)}

      {/* Panneau d'édition inline */}
      {peutEcrire && editId !== null && (
        <Card titre={`✏️ Modifier l'axe #${editId}`}>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="flex flex-col gap-1 text-fluid-sm font-medium">
              Nom
              <input
                type="text"
                value={editNom}
                onChange={(e) => setEditNom(e.target.value)}
                className="rounded-md border app-border app-surface px-3 py-2 text-fluid-base
                           focus:outline-none focus:ring-2 focus:ring-paa-blue-400 min-h-[42px]"
              />
            </label>
            <label className="flex flex-col gap-1 text-fluid-sm font-medium">
              Couleur
              <input
                type="color"
                value={editCouleur}
                onChange={(e) => setEditCouleur(e.target.value)}
                className="h-10 w-20 rounded border app-border cursor-pointer"
              />
            </label>
            <label className="flex flex-col gap-1 text-fluid-sm font-medium">
              Vitesse de référence (km/h)
              <input
                type="number"
                step={1}
                min={10}
                max={130}
                value={editVitesse}
                onChange={(e) => setEditVitesse(Number(e.target.value))}
                className="rounded-md border app-border app-surface px-3 py-2 text-fluid-base
                           focus:outline-none focus:ring-2 focus:ring-paa-blue-400 min-h-[42px]"
              />
            </label>
            <div />
            <label className="flex flex-col gap-1 text-fluid-sm font-medium">
              Latitude origine
              <input
                type="text"
                inputMode="decimal"
                value={editLatOrig}
                onChange={(e) => setEditLatOrig(e.target.value)}
                className="rounded-md border app-border app-surface px-3 py-2 text-fluid-base font-mono
                           focus:outline-none focus:ring-2 focus:ring-paa-blue-400 min-h-[42px]"
              />
            </label>
            <label className="flex flex-col gap-1 text-fluid-sm font-medium">
              Longitude origine
              <input
                type="text"
                inputMode="decimal"
                value={editLonOrig}
                onChange={(e) => setEditLonOrig(e.target.value)}
                className="rounded-md border app-border app-surface px-3 py-2 text-fluid-base font-mono
                           focus:outline-none focus:ring-2 focus:ring-paa-blue-400 min-h-[42px]"
              />
            </label>
            <label className="flex flex-col gap-1 text-fluid-sm font-medium">
              Latitude destination
              <input
                type="text"
                inputMode="decimal"
                value={editLatDest}
                onChange={(e) => setEditLatDest(e.target.value)}
                className="rounded-md border app-border app-surface px-3 py-2 text-fluid-base font-mono
                           focus:outline-none focus:ring-2 focus:ring-paa-blue-400 min-h-[42px]"
              />
            </label>
            <label className="flex flex-col gap-1 text-fluid-sm font-medium">
              Longitude destination
              <input
                type="text"
                inputMode="decimal"
                value={editLonDest}
                onChange={(e) => setEditLonDest(e.target.value)}
                className="rounded-md border app-border app-surface px-3 py-2 text-fluid-base font-mono
                           focus:outline-none focus:ring-2 focus:ring-paa-blue-400 min-h-[42px]"
              />
            </label>
          </div>
          <p className="mt-2 text-fluid-xs app-text-muted">
            Si vous modifiez une coordonnée, la polyline et la distance sont recalculées automatiquement (OSRM si disponible, sinon segment droit). Les sous-tronçons de cet axe sont réordonnés par distance GPS.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={enregistrerEdition}
              disabled={editEnCours || !editNom.trim()}
              className="btn-primary disabled:opacity-50 min-h-[42px]"
            >
              {editEnCours ? "Enregistrement…" : "💾 Enregistrer"}
            </button>
            <button
              type="button"
              onClick={annulerEdition}
              className="btn-secondary min-h-[42px]"
            >
              ✕ Annuler
            </button>
          </div>
          {editErreur && (
            <div className="mt-3 rounded-md bg-statut-congestionne/10 border border-statut-congestionne/40 px-3 py-2 text-fluid-sm text-statut-congestionne">
              {editErreur}
            </div>
          )}
        </Card>
      )}

      <Card titre={`${troncons.filter((t) => t.actif).length} axe${troncons.filter((t) => t.actif).length > 1 ? "s" : ""} actif${troncons.filter((t) => t.actif).length > 1 ? "s" : ""}`}>
        <div className="overflow-x-auto">
          <table className="min-w-full text-fluid-sm">
            <thead className="bg-paa-blue-50 dark:bg-paa-navy-800">
              <tr className="text-left">
                <th className="px-3 py-2 font-medium">ID</th>
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
                  <td className="px-3 py-2 whitespace-nowrap">
                    {t.actif ? (
                      <div className="flex gap-2">
                        {peutEcrire && (
                          <button
                            type="button"
                            onClick={() => ouvrirEdition(t)}
                            className="text-fluid-xs text-paa-navy-700 dark:text-paa-blue-200 hover:underline"
                          >
                            ✏️ Modifier
                          </button>
                        )}
                        {peutEcrire && (
                          <button
                            type="button"
                            onClick={() => archiver(t)}
                            className="text-fluid-xs text-statut-congestionne hover:underline"
                          >
                            🗄 Archiver
                          </button>
                        )}
                      </div>
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

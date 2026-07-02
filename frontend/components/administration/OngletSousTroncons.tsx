"use client";

/**
 * Onglet "Tronçons codifiés" — DEESP convention (T1A, T1B, T1C...).
 *
 * L'agent sélectionne un axe parent, place 2 markers (début, fin)
 * du tronçon sur la polyline parent visible en surbrillance, et
 * saisit le code (T1A...) + un nom court.
 */

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";

import { Card } from "@/components/ui/Card";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import type { SousTroncon, TronconAdmin } from "@/lib/types";

const CarteAdmin = dynamic(
  () => import("@/components/administration/CarteAdmin").then((m) => m.CarteAdmin),
  { ssr: false },
);

export function OngletSousTroncons({
  troncons,
}: {
  troncons: TronconAdmin[];
}) {
  const { peutEcrire } = useAuth();
  const [parentId, setParentId] = useState<number | null>(null);
  const [sousTroncons, setSousTroncons] = useState<SousTroncon[]>([]);
  const [code, setCode] = useState<string>("");
  const [nomCourt, setNomCourt] = useState<string>("");
  const [debut, setDebut] = useState<{ lat: number; lon: number } | null>(null);
  const [fin, setFin] = useState<{ lat: number; lon: number } | null>(null);
  const [pointActif, setPointActif] = useState<"debut" | "fin" | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [succes, setSucces] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  // 1er parent par défaut
  useEffect(() => {
    if (parentId === null && troncons.length > 0) {
      setParentId(troncons[0].id);
    }
  }, [parentId, troncons]);

  // Charger les sous-tronçons du parent
  const chargerSousTroncons = useCallback(async () => {
    if (parentId === null) return;
    try {
      const r = await api.sousTroncons(parentId);
      setSousTroncons(r.sous_troncons);
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    }
  }, [parentId]);

  useEffect(() => {
    void chargerSousTroncons();
  }, [chargerSousTroncons]);

  const reinitialiser = () => {
    setCode("");
    setNomCourt("");
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
    if (parentId === null) {
      setErreur("Choisissez un tronçon parent.");
      return;
    }
    if (!code.trim() || !nomCourt.trim() || !debut || !fin) {
      setErreur("Code + nom court + 2 markers obligatoires.");
      return;
    }
    setEnCours(true);
    setErreur(null);
    setSucces(null);
    try {
      const s = await api.creerSousTroncon(parentId, {
        code: code.trim().toUpperCase(),
        nom_court: nomCourt.trim(),
        lat_debut: debut.lat,
        lon_debut: debut.lon,
        lat_fin: fin.lat,
        lon_fin: fin.lon,
      });
      setSucces(`✅ Tronçon créé : ${s.code} (${s.distance_m} m)`);
      reinitialiser();
      void chargerSousTroncons();
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setEnCours(false);
    }
  };

  const archiver = async (s: SousTroncon) => {
    if (!confirm(`Archiver le tronçon ${s.code} ?`)) return;
    try {
      await api.supprimerSousTroncon(s.id);
      void chargerSousTroncons();
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    }
  };

  const parent = troncons.find((t) => t.id === parentId);
  // Suggérer le prochain code (T<n><lettre> selon ordre)
  const lettresUtilisees = sousTroncons.map((s) => s.code.slice(-1).toUpperCase());
  const prochaineLettre = "ABCDEFGHIJ".split("").find((l) => !lettresUtilisees.includes(l)) ?? "Z";
  const codeSuggere = parentId !== null ? `T${parentId}${prochaineLettre}` : "";

  return (
    <div className="flex flex-col gap-fluid-4">
      {/* Sélecteur parent */}
      <Card titre="Axe parent">
        <label className="flex flex-col gap-1 text-fluid-sm font-medium">
          Choisir l'axe parent
          <select
            value={parentId ?? ""}
            onChange={(e) => setParentId(Number(e.target.value))}
            className="rounded-md border app-border app-surface px-3 py-2 text-fluid-base
                       focus:outline-none focus:ring-2 focus:ring-paa-blue-400 min-h-[42px]"
          >
            {(() => {
              const actifs = troncons.filter((t) => t.actif);
              const axes = actifs.filter((t) => t.est_axe ?? (t.id <= 6));
              const autres = actifs.filter((t) => !(t.est_axe ?? (t.id <= 6)));
              return (<>
                <optgroup label="── Axes officiels DEESP ──">
                  {axes.map((t) => <option key={t.id} value={t.id}>{t.nom}</option>)}
                </optgroup>
                {autres.length > 0 && (
                  <optgroup label="── Tronçons supplémentaires ──">
                    {autres.map((t) => <option key={t.id} value={t.id}>{t.nom}</option>)}
                  </optgroup>
                )}
              </>);
            })()}
          </select>
        </label>
      </Card>

      {/* Formulaire de création + carte — masqués en mode lecture */}
      {peutEcrire && (<><Card
        titre={`Ajouter un tronçon à ${parent?.nom ?? "…"}`}
        description={`Convention DEESP : T<n>A, T<n>B... (suggéré : ${codeSuggere}). Placez début et fin sur la polyline parent.`}
      >
        <div className="grid gap-3 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-fluid-sm font-medium">
            Code
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              placeholder={codeSuggere}
              maxLength={10}
              className="rounded-md border app-border app-surface px-3 py-2 text-fluid-base font-mono
                         focus:outline-none focus:ring-2 focus:ring-paa-blue-400 min-h-[42px]"
            />
          </label>
          <label className="flex flex-col gap-1 text-fluid-sm font-medium">
            Nom court
            <input
              type="text"
              value={nomCourt}
              onChange={(e) => setNomCourt(e.target.value)}
              placeholder="ex. Pont Houphouët-Boigny"
              className="rounded-md border app-border app-surface px-3 py-2 text-fluid-base
                         focus:outline-none focus:ring-2 focus:ring-paa-blue-400 min-h-[42px]"
            />
          </label>
        </div>

        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <div className="rounded-md border app-border p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-fluid-xs font-medium app-text-muted">
                🟢 Début tronçon
              </span>
              <button
                type="button"
                onClick={() => setPointActif(pointActif === "debut" ? null : "debut")}
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
              <p className="text-fluid-xs app-text-muted">À placer sur la carte</p>
            )}
          </div>
          <div className="rounded-md border app-border p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-fluid-xs font-medium app-text-muted">
                🔴 Fin tronçon
              </span>
              <button
                type="button"
                onClick={() => setPointActif(pointActif === "fin" ? null : "fin")}
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
              <p className="text-fluid-xs app-text-muted">À placer sur la carte</p>
            )}
          </div>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={valider}
            disabled={enCours || !code || !nomCourt || !debut || !fin || parentId === null}
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
          <div className="mt-3 rounded-md bg-statut-congestionne/10 border border-statut-congestionne/40 px-3 py-2 text-fluid-sm text-statut-congestionne">
            {erreur}
          </div>
        )}
        {succes && (
          <div className="mt-3 rounded-md bg-statut-fluide/10 border border-statut-fluide/40 px-3 py-2 text-fluid-sm text-statut-fluide">
            {succes}
          </div>
        )}
      </Card>

      {/* Carte */}
      <Card titre="Polyline parent + tronçon en cours">
        <CarteAdmin
          pointActif={pointActif}
          debut={debut}
          fin={fin}
          polylinesParent={
            parent
              ? [{
                  id: parent.id,
                  polyline: parent.polyline ?? null,
                  couleur: parent.couleur,
                  lat_origine: parent.lat_origine,
                  lon_origine: parent.lon_origine,
                  lat_destination: parent.lat_destination,
                  lon_destination: parent.lon_destination,
                  nom: parent.nom,
                }]
              : []
          }
          onClick={handleClickCarte}
        />
      </Card>
      </>)}

      {/* Liste des sous-tronçons */}
      <Card titre={`Tronçons existants (${sousTroncons.length})`}>
        <div className="overflow-x-auto">
          <table className="min-w-full text-fluid-sm">
            <thead className="bg-paa-blue-50 dark:bg-paa-navy-800">
              <tr className="text-left">
                <th className="px-3 py-2 font-medium">Code</th>
                <th className="px-3 py-2 font-medium">Nom court</th>
                <th className="px-3 py-2 font-medium text-right">Ordre</th>
                <th className="px-3 py-2 font-medium text-right">Distance</th>
                <th className="px-3 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sousTroncons.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-3 py-4 text-center app-text-muted text-fluid-xs">
                    Aucun tronçon défini pour cet axe.
                  </td>
                </tr>
              ) : (
                sousTroncons.map((s) => (
                  <tr key={s.id} className="border-t app-border">
                    <td className="px-3 py-2 font-mono font-semibold">{s.code}</td>
                    <td className="px-3 py-2">{s.nom_court}</td>
                    <td className="px-3 py-2 text-right">{s.ordre}</td>
                    <td className="px-3 py-2 text-right">{s.distance_m} m</td>
                    <td className="px-3 py-2">
                      <button
                        type="button"
                        onClick={() => archiver(s)}
                        className="text-fluid-xs text-statut-congestionne hover:underline"
                      >
                        🗄 Archiver
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

"use client";

/**
 * Onglet "Tronçons codifiés" — DEESP convention (T1A, T1B, T1C...).
 *
 * L'agent sélectionne un axe parent, place 2 markers (début, fin)
 * du tronçon sur la polyline parent visible en surbrillance, et
 * saisit le code (T1A...) + un nom court.
 */

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AutocompleteLieu } from "@/components/administration/AutocompleteLieu";
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
  const [modeAvance, setModeAvance] = useState<boolean>(false);
  // Multi-parent (P12.2) : axes secondaires cochés en plus du parent principal
  const [axesSecondaires, setAxesSecondaires] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (parentId === null && troncons.length > 0) {
      const premierAxe = troncons.find((t) => t.actif && (t.est_axe ?? (t.id <= 6)));
      if (premierAxe) setParentId(premierAxe.id);
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
    setAxesSecondaires(new Set());
  };

  const basculerAxeSecondaire = (id: number) => {
    setAxesSecondaires((prec) => {
      const nouv = new Set(prec);
      if (nouv.has(id)) nouv.delete(id);
      else nouv.add(id);
      return nouv;
    });
  };

  const axesDispo = useMemo(
    () => troncons.filter((t) => t.actif && (t.est_axe ?? (t.id <= 6))),
    [troncons],
  );

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
      const secondairesTries = Array.from(axesSecondaires).filter((id) => id !== parentId);
      const s = await api.creerSousTroncon(parentId, {
        code: code.trim().toUpperCase(),
        nom_court: nomCourt.trim(),
        lat_debut: debut.lat,
        lon_debut: debut.lon,
        lat_fin: fin.lat,
        lon_fin: fin.lon,
        ...(secondairesTries.length > 0 ? { axe_ids: [parentId, ...secondairesTries] } : {}),
      });
      const nbParents = 1 + secondairesTries.length;
      setSucces(
        `✅ Tronçon créé : ${s.code} (${s.distance_m} m)`
        + (nbParents > 1 ? ` — rattaché à ${nbParents} axes parents.` : "")
      );
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

  // --- Édition inline d'un sous-tronçon existant ---
  const [editId, setEditId] = useState<number | null>(null);
  const [editCode, setEditCode] = useState<string>("");
  const [editNomCourt, setEditNomCourt] = useState<string>("");
  const [editLatDebut, setEditLatDebut] = useState<string>("");
  const [editLonDebut, setEditLonDebut] = useState<string>("");
  const [editLatFin, setEditLatFin] = useState<string>("");
  const [editLonFin, setEditLonFin] = useState<string>("");
  const [editAxes, setEditAxes] = useState<Set<number>>(new Set());
  const [editErreur, setEditErreur] = useState<string | null>(null);
  const [editEnCours, setEditEnCours] = useState<boolean>(false);

  const ouvrirEdition = (s: SousTroncon) => {
    setEditId(s.id);
    setEditCode(s.code);
    setEditNomCourt(s.nom_court);
    setEditLatDebut(String(s.lat_debut ?? ""));
    setEditLonDebut(String(s.lon_debut ?? ""));
    setEditLatFin(String(s.lat_fin ?? ""));
    setEditLonFin(String(s.lon_fin ?? ""));
    setEditAxes(new Set(s.axe_ids ?? [s.troncon_id]));
    setEditErreur(null);
  };

  const annulerEdition = () => setEditId(null);

  const basculerEditAxe = (id: number) => {
    setEditAxes((prec) => {
      const n = new Set(prec);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  };

  const enregistrerEdition = async () => {
    if (editId === null) return;
    setEditEnCours(true);
    setEditErreur(null);
    try {
      const payload: Parameters<typeof api.majSousTroncon>[1] = {
        code: editCode.trim().toUpperCase(),
        nom_court: editNomCourt.trim(),
      };
      const parseNum = (s: string) => (s.trim() === "" ? undefined : Number(s));
      const a = parseNum(editLatDebut);
      const b = parseNum(editLonDebut);
      const c = parseNum(editLatFin);
      const d = parseNum(editLonFin);
      if (a !== undefined) payload.lat_debut = a;
      if (b !== undefined) payload.lon_debut = b;
      if (c !== undefined) payload.lat_fin = c;
      if (d !== undefined) payload.lon_fin = d;
      if (editAxes.size > 0) payload.axe_ids = Array.from(editAxes);
      await api.majSousTroncon(editId, payload);
      setEditId(null);
      void chargerSousTroncons();
    } catch (e) {
      setEditErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setEditEnCours(false);
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
            {troncons
              .filter((t) => t.actif && (t.est_axe ?? (t.id <= 6)))
              .map((t) => <option key={t.id} value={t.id}>{t.nom}</option>)
            }
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

        {/* Autocomplétion des lieux */}
        <div className="mt-3 rounded-lg border app-border bg-paa-blue-50/40 dark:bg-paa-navy-800/40 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-fluid-sm font-semibold text-paa-navy-700 dark:text-paa-blue-200">
              📍 Saisie par nom d&apos;endroit
            </h3>
            <button
              type="button"
              onClick={() => setModeAvance((v) => !v)}
              className="text-fluid-xs text-paa-navy-700 dark:text-paa-blue-200 hover:underline"
            >
              {modeAvance ? "▲ Masquer mode avancé" : "▼ Mode avancé (clic carte)"}
            </button>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <AutocompleteLieu
              label="Début du tronçon"
              couleurBadge="#16a34a"
              placeholder="ex. Sim Ivoire, Boulevard de Marseille"
              onSelect={(_nom, lat, lon) => setDebut({ lat, lon })}
              onEffacer={() => setDebut(null)}
            />
            <AutocompleteLieu
              label="Fin du tronçon"
              couleurBadge="#dc2626"
              placeholder="ex. Carrefour Seamen's Club"
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
        </div>

        {/* Multi-parent : sélectionner d'autres axes qui contiennent ce même tronçon */}
        <div className="mt-3 rounded-lg border app-border bg-amber-50/60 dark:bg-amber-900/20 p-4">
          <h3 className="text-fluid-sm font-semibold text-paa-navy-700 dark:text-paa-blue-100 mb-1">
            🔗 Axes parents supplémentaires (optionnel)
          </h3>
          <p className="text-fluid-xs app-text-muted mb-3">
            Cochez d&apos;autres axes qui partagent ce même tronçon (par exemple un pont commun).
            Le tronçon apparaîtra sous chacun sans être dupliqué ni doublement mesuré.
            <br />
            Parent principal :{" "}
            <span className="font-medium">
              {axesDispo.find((t) => t.id === parentId)?.nom ?? "…"}
            </span>{" "}
            (toujours inclus)
          </p>
          <div className="grid gap-2 md:grid-cols-2">
            {axesDispo
              .filter((t) => t.id !== parentId)
              .map((t) => (
                <label
                  key={`ax-sec-${t.id}`}
                  className="flex items-center gap-2 rounded-md border app-border bg-white
                             dark:bg-paa-navy-900 px-3 py-2 text-fluid-xs cursor-pointer
                             hover:bg-paa-blue-50 dark:hover:bg-paa-navy-800"
                >
                  <input
                    type="checkbox"
                    checked={axesSecondaires.has(t.id)}
                    onChange={() => basculerAxeSecondaire(t.id)}
                    className="h-4 w-4 accent-paa-navy-700"
                  />
                  <span className="flex-1 truncate">{t.nom}</span>
                </label>
              ))}
          </div>
          {axesSecondaires.size > 0 && (
            <p className="mt-2 text-fluid-xs text-paa-navy-700 dark:text-paa-blue-200">
              ✓ Ce tronçon sera rattaché à {1 + axesSecondaires.size} axes
              parents au total.
            </p>
          )}
        </div>

        {/* Mode avancé — placement par clic sur la carte */}
        {modeAvance && (
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <div className="rounded-md border app-border p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-fluid-xs font-medium app-text-muted">
                🟢 Début (clic carte)
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
                🔴 Fin (clic carte)
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
        )}

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

      {/* Carte — uniquement en mode avancé */}
      {modeAvance && (
      <Card titre="Polyline parent + tronçon en cours (mode avancé)">
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
      )}
      </>)}

      {/* Panneau d'édition inline */}
      {peutEcrire && editId !== null && (
        <Card titre={`✏️ Modifier le tronçon #${editId}`}>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="flex flex-col gap-1 text-fluid-sm font-medium">
              Code
              <input
                type="text"
                value={editCode}
                onChange={(e) => setEditCode(e.target.value.toUpperCase())}
                maxLength={10}
                className="rounded-md border app-border app-surface px-3 py-2 text-fluid-base font-mono
                           focus:outline-none focus:ring-2 focus:ring-paa-blue-400 min-h-[42px]"
              />
            </label>
            <label className="flex flex-col gap-1 text-fluid-sm font-medium">
              Nom court
              <input
                type="text"
                value={editNomCourt}
                onChange={(e) => setEditNomCourt(e.target.value)}
                className="rounded-md border app-border app-surface px-3 py-2 text-fluid-base
                           focus:outline-none focus:ring-2 focus:ring-paa-blue-400 min-h-[42px]"
              />
            </label>
            <label className="flex flex-col gap-1 text-fluid-sm font-medium">
              Latitude début
              <input
                type="text"
                inputMode="decimal"
                value={editLatDebut}
                onChange={(e) => setEditLatDebut(e.target.value)}
                className="rounded-md border app-border app-surface px-3 py-2 text-fluid-base font-mono
                           focus:outline-none focus:ring-2 focus:ring-paa-blue-400 min-h-[42px]"
              />
            </label>
            <label className="flex flex-col gap-1 text-fluid-sm font-medium">
              Longitude début
              <input
                type="text"
                inputMode="decimal"
                value={editLonDebut}
                onChange={(e) => setEditLonDebut(e.target.value)}
                className="rounded-md border app-border app-surface px-3 py-2 text-fluid-base font-mono
                           focus:outline-none focus:ring-2 focus:ring-paa-blue-400 min-h-[42px]"
              />
            </label>
            <label className="flex flex-col gap-1 text-fluid-sm font-medium">
              Latitude fin
              <input
                type="text"
                inputMode="decimal"
                value={editLatFin}
                onChange={(e) => setEditLatFin(e.target.value)}
                className="rounded-md border app-border app-surface px-3 py-2 text-fluid-base font-mono
                           focus:outline-none focus:ring-2 focus:ring-paa-blue-400 min-h-[42px]"
              />
            </label>
            <label className="flex flex-col gap-1 text-fluid-sm font-medium">
              Longitude fin
              <input
                type="text"
                inputMode="decimal"
                value={editLonFin}
                onChange={(e) => setEditLonFin(e.target.value)}
                className="rounded-md border app-border app-surface px-3 py-2 text-fluid-base font-mono
                           focus:outline-none focus:ring-2 focus:ring-paa-blue-400 min-h-[42px]"
              />
            </label>
          </div>
          <div className="mt-3 rounded-md border app-border bg-amber-50/60 dark:bg-amber-900/20 p-3">
            <h4 className="text-fluid-sm font-semibold text-paa-navy-700 dark:text-paa-blue-100 mb-2">
              🔗 Axes parents rattachés
            </h4>
            <div className="grid gap-1 md:grid-cols-2">
              {axesDispo.map((t) => (
                <label
                  key={`ed-ax-${t.id}`}
                  className="flex items-center gap-2 rounded border app-border bg-white
                             dark:bg-paa-navy-900 px-2 py-1 text-fluid-xs cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={editAxes.has(t.id)}
                    onChange={() => basculerEditAxe(t.id)}
                    className="h-4 w-4 accent-paa-navy-700"
                  />
                  <span className="flex-1 truncate">{t.nom}</span>
                </label>
              ))}
            </div>
          </div>
          <p className="mt-2 text-fluid-xs app-text-muted">
            Coord modifiées → polyline + distance recalculées et sous-tronçons réordonnés sur chaque axe parent.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={enregistrerEdition}
              disabled={editEnCours || !editCode.trim() || !editNomCourt.trim()}
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

      {/* Liste des tronçons codifiés de l'axe sélectionné */}
      <Card titre={`Tronçons de ${parent?.nom ?? "…"} (${sousTroncons.length})`}>
        <div className="overflow-x-auto">
          <table className="min-w-full text-fluid-sm">
            <thead className="bg-paa-blue-50 dark:bg-paa-navy-800">
              <tr className="text-left">
                <th className="px-3 py-2 font-medium">Code</th>
                <th className="px-3 py-2 font-medium">Nom</th>
                <th className="px-3 py-2 font-medium text-right">Distance</th>
                <th className="px-3 py-2 font-medium">Axes</th>
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
                  <tr key={`st-${s.id}`} className="border-t app-border">
                    <td className="px-3 py-2 font-mono font-semibold">{s.code}</td>
                    <td className="px-3 py-2">{s.nom_court}</td>
                    <td className="px-3 py-2 text-right">{s.distance_m} m</td>
                    <td className="px-3 py-2 text-fluid-xs">
                      {(s.axe_ids ?? [s.troncon_id]).length > 1
                        ? `${(s.axe_ids ?? []).length} axes`
                        : "1 axe"}
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      {peutEcrire && (
                        <div className="flex gap-2">
                          <button
                            type="button"
                            onClick={() => ouvrirEdition(s)}
                            className="text-fluid-xs text-paa-navy-700 dark:text-paa-blue-200 hover:underline"
                          >
                            ✏️ Modifier
                          </button>
                          <button
                            type="button"
                            onClick={() => archiver(s)}
                            className="text-fluid-xs text-statut-congestionne hover:underline"
                          >
                            🗄 Archiver
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Récapitulatif de tous les axes */}
      <Card titre={`Tous les axes (${troncons.filter((t) => t.actif).length})`}>
        <div className="overflow-x-auto">
          <table className="min-w-full text-fluid-sm">
            <thead className="bg-paa-blue-50 dark:bg-paa-navy-800">
              <tr className="text-left">
                <th className="px-3 py-2 font-medium">ID</th>
                <th className="px-3 py-2 font-medium">Nom</th>
                <th className="px-3 py-2 font-medium text-right">Distance</th>
                <th className="px-3 py-2 font-medium">Couleur</th>
              </tr>
            </thead>
            <tbody>
              {troncons.filter((t) => t.actif).map((t) => (
                <tr key={t.id} className="border-t app-border">
                  <td className="px-3 py-2 font-mono">{t.id}</td>
                  <td className="px-3 py-2">{t.nom}</td>
                  <td className="px-3 py-2 text-right">{t.distance_km} km</td>
                  <td className="px-3 py-2">
                    <span
                      className="inline-block h-4 w-4 rounded border app-border align-middle"
                      style={{ backgroundColor: t.couleur }}
                    />
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

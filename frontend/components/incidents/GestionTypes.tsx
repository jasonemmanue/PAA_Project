"use client";

/**
 * Gestion des types d'incidents configurables (migration 0015).
 *
 * - Liste les types actifs/inactifs
 * - Permet d'activer / désactiver un type (toggle)
 * - Permet d'ajouter un type personnalisé (slug + libellé + regex)
 * - Permet de supprimer un type (sauf 'autre')
 * Visible uniquement en mode écriture.
 */

import { useEffect, useState } from "react";

import { useAuth } from "@/contexts/AuthContext";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8081";

interface TypeApi {
  id: number;
  slug: string;
  libelle: string;
  regex: string;
  actif: boolean;
  cree_le: string;
}

const TYPE_VIDE = {
  slug: "", libelle: "", mots: "", actif: true,
};

// Convertit une liste de mots-clés séparés par virgule/point-virgule en regex Python
function motsVersRegex(mots: string): string {
  return mots
    .split(/[,;]+/)
    .map((m) => m.trim().toLowerCase())
    .filter(Boolean)
    .join("|");
}

// Slugifie automatiquement le libellé saisi
function slugifier(s: string): string {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 40);
}

interface Props {
  // Appelé après chaque ajout / suppression / toggle pour que le filtre se mette à jour
  onTypeChange?: () => void;
}

export function GestionTypes({ onTypeChange }: Props) {
  const { peutEcrire } = useAuth();
  const [types, setTypes] = useState<TypeApi[]>([]);
  const [ouvert, setOuvert] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [form, setForm] = useState(TYPE_VIDE);

  async function recharger() {
    try {
      const rep = await fetch(`${API_BASE}/incidents/types`);
      if (rep.ok) {
        const data = await rep.json();
        setTypes(data);
        onTypeChange?.();   // notifie PageIncidents → filtre mis à jour instantanément
      } else setTypes([]);
    } catch {
      setTypes([]);
    }
  }

  useEffect(() => {
    if (ouvert) {
      setErreur(null);
      recharger();
    }
  }, [ouvert]);

  useEffect(() => {
    if (!erreur) return;
    const id = setTimeout(() => setErreur(null), 6000);
    return () => clearTimeout(id);
  }, [erreur]);

  async function ajouter() {
    setEnCours(true); setErreur(null);
    try {
      const regex = motsVersRegex(form.mots);
      if (!regex) { setErreur("Entrez au moins un mot-clé."); setEnCours(false); return; }
      const payload = {
        slug: form.slug || slugifier(form.libelle),
        libelle: form.libelle,
        regex,
        actif: true,
      };
      const rep = await fetch(`${API_BASE}/incidents/types`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!rep.ok) {
        const data = await rep.json().catch(() => ({}));
        const detail = data?.detail ?? `Erreur HTTP ${rep.status}`;
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      }
      setForm(TYPE_VIDE);
      await recharger();
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setEnCours(false);
    }
  }

  async function basculerActif(t: TypeApi) {
    try {
      const rep = await fetch(`${API_BASE}/incidents/types/${t.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actif: !t.actif }),
      });
      if (!rep.ok) throw new Error(`HTTP ${rep.status}`);
      await recharger();
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    }
  }

  async function supprimer(t: TypeApi) {
    if (!confirm(`Supprimer définitivement le type "${t.libelle}" ?`)) return;
    try {
      const rep = await fetch(`${API_BASE}/incidents/types/${t.id}`, {
        method: "DELETE",
      });
      if (!rep.ok) {
        const data = await rep.json().catch(() => ({}));
        throw new Error(data?.detail ?? `HTTP ${rep.status}`);
      }
      await recharger();
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    }
  }

  if (!peutEcrire) return null;

  return (
    <div className="paa-card p-4">
      <button
        type="button"
        onClick={() => setOuvert((v) => !v)}
        className="flex w-full items-center justify-between text-left"
      >
        <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">
          🏷 Gérer les types d'incidents ({types.length || "…"})
        </span>
        <span className="text-xs text-gray-500">{ouvert ? "▲" : "▼"}</span>
      </button>

      {ouvert && (
        <div className="mt-3 flex flex-col gap-3">
          {erreur && (
            <div className="flex items-start justify-between gap-2 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-700 dark:bg-red-950/30 dark:text-red-300">
              <span>{erreur}</span>
              <button
                type="button"
                onClick={() => setErreur(null)}
                className="shrink-0 rounded px-1 font-bold opacity-70 hover:opacity-100"
              >
                ✕
              </button>
            </div>
          )}

          {/* Liste */}
          <div className="overflow-x-auto rounded-md border app-border">
            <table className="min-w-full text-sm">
              <thead className="bg-paa-blue-50 dark:bg-paa-navy-800">
                <tr className="text-left">
                  <th className="px-3 py-2 font-medium">Libellé</th>
                  <th className="px-3 py-2 font-medium">Mots-clés détectés</th>
                  <th className="px-3 py-2 font-medium text-center">Actif</th>
                  <th className="px-3 py-2 font-medium text-center">Actions</th>
                </tr>
              </thead>
              <tbody>
                {types.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-3 py-4 text-center text-gray-500">
                      Aucun type configuré.
                    </td>
                  </tr>
                )}
                {types.filter((type) => type.slug !== "autre").map((type) => (
                  <tr key={type.id} className="border-t app-border">
                    <td className="px-3 py-2 font-medium">{type.libelle}</td>
                    <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-300 max-w-[260px]"
                        title={type.regex}>
                      {type.regex
                        .split("|")
                        .slice(0, 5)
                        .map((m) => (
                          <span key={m} className="inline-block mr-1 mb-1 px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700">
                            {m}
                          </span>
                        ))}
                      {type.regex.split("|").length > 5 && (
                        <span className="text-gray-400">+{type.regex.split("|").length - 5}</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-center">
                      <button
                        onClick={() => basculerActif(type)}
                        className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                          type.actif
                            ? "bg-statut-fluide/20 text-statut-fluide"
                            : "bg-gray-300 text-gray-700 dark:bg-gray-700 dark:text-gray-300"
                        }`}
                      >
                        {type.actif ? "✓ ON" : "✗ OFF"}
                      </button>
                    </td>
                    <td className="px-3 py-2 text-center">
                      {type.slug !== "autre" ? (
                        <button
                          onClick={() => supprimer(type)}
                          className="text-xs text-statut-congestionne hover:underline"
                        >
                          Supprimer
                        </button>
                      ) : (
                        <span className="text-xs text-gray-400 italic">défaut</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Formulaire ajout */}
          <fieldset className="rounded-md border border-dashed app-border p-4">
            <legend className="px-2 text-sm font-semibold app-text-muted">
              ➕ Ajouter un type d'incident
            </legend>

            <div className="grid gap-3">
              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium app-text-muted">
                  Libellé affiché <span className="text-statut-congestionne">*</span>
                </span>
                <input
                  type="text"
                  placeholder="Ex. Incendie / explosion"
                  value={form.libelle}
                  onChange={(e) => setForm({
                    ...form,
                    libelle: e.target.value,
                    slug: slugifier(e.target.value),
                  })}
                  className="rounded border app-border px-3 py-2 text-sm app-surface"
                />
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium app-text-muted">
                  Mots-clés de détection <span className="text-statut-congestionne">*</span>
                  <span className="ml-1 font-normal text-gray-400">(séparés par des virgules)</span>
                </span>
                <input
                  type="text"
                  placeholder="Ex. incendie, explosion, feu de véhicule, fumée"
                  value={form.mots}
                  onChange={(e) => setForm({ ...form, mots: e.target.value })}
                  className="rounded border app-border px-3 py-2 text-sm app-surface"
                />
              </label>

              {/* Aperçu de la regex générée */}
              {form.mots.trim() && (
                <div className="rounded-md bg-gray-50 dark:bg-gray-800/60 border app-border px-3 py-2 text-xs">
                  <span className="text-gray-500 dark:text-gray-400">Règle générée : </span>
                  <span className="font-mono text-paa-navy-700 dark:text-paa-blue-300">
                    {motsVersRegex(form.mots)}
                  </span>
                </div>
              )}

              {/* Lien vers le chatbot */}
              <p className="text-xs text-gray-500 dark:text-gray-400">
                💬 Vous ne savez pas quels mots-clés utiliser ?{" "}
                <span className="text-paa-blue-600 dark:text-paa-blue-400">
                  Demandez à l&apos;assistant PAA (bouton Aide en bas à droite) :
                  « Quels mots-clés utiliser pour détecter des incidents de type{" "}
                  {form.libelle || "…"} dans la presse ivoirienne ? »
                </span>
              </p>

              <button
                type="button"
                onClick={ajouter}
                disabled={
                  enCours ||
                  !form.libelle || form.libelle.length < 2 ||
                  !form.mots.trim()
                }
                className="w-full rounded-md bg-paa-blue-500 px-4 py-2 text-sm font-semibold text-white
                           shadow-paa-sm hover:bg-paa-blue-600 transition-colors
                           disabled:cursor-not-allowed disabled:opacity-50"
              >
                {enCours ? "Ajout en cours…" : "Ajouter ce type"}
              </button>
            </div>

            <p className="mt-3 text-xs app-text-muted">
              ℹ️ Le classificateur NLP appliquera ces mots-clés à la prochaine
              exécution de l'enrichissement (automatique après chaque scraping).
            </p>
          </fieldset>
        </div>
      )}
    </div>
  );
}

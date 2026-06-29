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
  slug: "", libelle: "", regex: "", actif: true,
};

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

export function GestionTypes() {
  const { peutEcrire } = useAuth();
  const [types, setTypes] = useState<TypeApi[]>([]);
  const [ouvert, setOuvert] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [form, setForm] = useState(TYPE_VIDE);

  async function recharger() {
    try {
      const rep = await fetch(`${API_BASE}/incidents/types`);
      if (rep.ok) setTypes(await rep.json());
      else setTypes([]);
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
      const payload = {
        ...form,
        slug: form.slug || slugifier(form.libelle),
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
                  <th className="px-3 py-2 font-medium">Slug</th>
                  <th className="px-3 py-2 font-medium">Regex de détection</th>
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
                {types.map((type) => (
                  <tr key={type.id} className="border-t app-border">
                    <td className="px-3 py-2 font-medium">{type.libelle}</td>
                    <td className="px-3 py-2 font-mono text-xs text-gray-500">{type.slug}</td>
                    <td className="px-3 py-2 font-mono text-xs truncate max-w-[220px]"
                        title={type.regex}>
                      {type.regex}
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

            <div className="mb-3 rounded-md bg-paa-blue-50 dark:bg-paa-navy-800/60 border border-paa-blue-200 dark:border-paa-navy-600 p-3 text-xs">
              <p className="font-semibold text-paa-navy-800 dark:text-paa-blue-100 mb-1">
                💡 Exemple
              </p>
              <ul className="space-y-1 text-paa-navy-700 dark:text-paa-blue-200">
                <li><b>Libellé</b> : Incendie / explosion</li>
                <li><b>Regex</b> : incendie|explosion|feu de véhicule</li>
              </ul>
              <p className="mt-2 italic text-paa-navy-600 dark:text-paa-blue-300">
                La regex est insensible à la casse. Utilisez <span className="font-mono">|</span> pour
                séparer les alternatives. Le classificateur NLP l'utilisera au prochain cycle
                d'enrichissement (après chaque scraping).
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="flex flex-col gap-1 sm:col-span-2">
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

              <label className="flex flex-col gap-1 sm:col-span-2">
                <span className="text-xs font-medium app-text-muted">
                  Regex de détection <span className="text-statut-congestionne">*</span>
                </span>
                <input
                  type="text"
                  placeholder="Ex. incendie|explosion|feu de v"
                  value={form.regex}
                  onChange={(e) => setForm({ ...form, regex: e.target.value })}
                  className="rounded border app-border px-3 py-2 text-sm app-surface font-mono"
                />
              </label>

              <div className="flex items-end sm:col-span-2">
                <button
                  type="button"
                  onClick={ajouter}
                  disabled={
                    enCours ||
                    !form.libelle || form.libelle.length < 2 ||
                    !form.regex || form.regex.length < 1
                  }
                  className="w-full rounded-md bg-paa-blue-500 px-4 py-2 text-sm font-semibold text-white
                             shadow-paa-sm hover:bg-paa-blue-600 transition-colors
                             disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {enCours ? "Ajout en cours…" : "Ajouter ce type"}
                </button>
              </div>
            </div>

            <p className="mt-3 text-xs app-text-muted">
              ℹ️ Le classificateur NLP appliquera cette règle à la prochaine
              exécution de l'enrichissement (automatique après chaque scraping).
            </p>
          </fieldset>
        </div>
      )}
    </div>
  );
}

"use client";

/**
 * Gestion des sources de scraping incidents (migration 0014).
 *
 * - Liste les sources actuelles (lecture)
 * - Permet d'en ajouter / désactiver / supprimer (écriture)
 * Visible uniquement en mode écriture.
 */

import { useEffect, useState } from "react";

import { useAuth } from "@/contexts/AuthContext";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8081";

interface Source {
  id: number;
  nom: string;
  libelle: string;
  url: string;
  type: "rss" | "html";
  actif: boolean;
  fiabilite: number;
  ajoute_le: string;
}

const SOURCE_VIDE = {
  nom: "", libelle: "", url: "", type: "rss" as const,
  actif: true, fiabilite: 0.7,
};

export function GestionSources() {
  const { peutEcrire } = useAuth();
  const [sources, setSources] = useState<Source[]>([]);
  const [ouvert, setOuvert] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [form, setForm] = useState(SOURCE_VIDE);

  async function recharger() {
    try {
      const rep = await fetch(`${API_BASE}/incidents/sources`);
      if (!rep.ok) throw new Error(`HTTP ${rep.status}`);
      setSources(await rep.json());
      setErreur(null);
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    if (ouvert) recharger();
  }, [ouvert]);

  async function ajouter() {
    setEnCours(true); setErreur(null);
    try {
      const rep = await fetch(`${API_BASE}/incidents/sources`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!rep.ok) {
        const txt = await rep.text().catch(() => "");
        throw new Error(`HTTP ${rep.status} — ${txt}`);
      }
      setForm(SOURCE_VIDE);
      await recharger();
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setEnCours(false);
    }
  }

  async function basculerActif(s: Source) {
    try {
      const rep = await fetch(`${API_BASE}/incidents/sources/${s.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...s, actif: !s.actif }),
      });
      if (!rep.ok) throw new Error(`HTTP ${rep.status}`);
      await recharger();
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    }
  }

  async function supprimer(s: Source) {
    if (!confirm(`Supprimer définitivement la source "${s.libelle}" ?`)) return;
    try {
      const rep = await fetch(`${API_BASE}/incidents/sources/${s.id}`, {
        method: "DELETE",
      });
      if (!rep.ok) throw new Error(`HTTP ${rep.status}`);
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
          ⚙ Gérer les sources de scraping ({sources.length || "…"})
        </span>
        <span className="text-xs text-gray-500">{ouvert ? "▲" : "▼"}</span>
      </button>

      {ouvert && (
        <div className="mt-3 flex flex-col gap-3">
          {erreur && (
            <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-700 dark:bg-red-950/30 dark:text-red-300">
              {erreur}
            </div>
          )}

          {/* Liste */}
          <div className="overflow-x-auto rounded-md border app-border">
            <table className="min-w-full text-sm">
              <thead className="bg-paa-blue-50 dark:bg-paa-navy-800">
                <tr className="text-left">
                  <th className="px-3 py-2 font-medium">Libellé</th>
                  <th className="px-3 py-2 font-medium">URL</th>
                  <th className="px-3 py-2 font-medium">Type</th>
                  <th className="px-3 py-2 font-medium text-center">Fiab.</th>
                  <th className="px-3 py-2 font-medium text-center">Actif</th>
                  <th className="px-3 py-2 font-medium text-center">Actions</th>
                </tr>
              </thead>
              <tbody>
                {sources.length === 0 && (
                  <tr><td colSpan={6} className="px-3 py-4 text-center text-gray-500">
                    Aucune source configurée.
                  </td></tr>
                )}
                {sources.map((s) => (
                  <tr key={s.id} className="border-t app-border">
                    <td className="px-3 py-2 font-medium">{s.libelle}</td>
                    <td className="px-3 py-2 font-mono text-xs truncate max-w-[280px]">
                      <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-paa-blue-600 hover:underline">
                        {s.url}
                      </a>
                    </td>
                    <td className="px-3 py-2 uppercase font-mono text-xs">{s.type}</td>
                    <td className="px-3 py-2 text-center">{(s.fiabilite * 100).toFixed(0)}%</td>
                    <td className="px-3 py-2 text-center">
                      <button onClick={() => basculerActif(s)}
                              className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                                s.actif
                                  ? "bg-statut-fluide/20 text-statut-fluide"
                                  : "bg-gray-300 text-gray-700 dark:bg-gray-700 dark:text-gray-300"
                              }`}>
                        {s.actif ? "✓ ON" : "✗ OFF"}
                      </button>
                    </td>
                    <td className="px-3 py-2 text-center">
                      <button onClick={() => supprimer(s)}
                              className="text-xs text-statut-congestionne hover:underline">
                        Supprimer
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Formulaire ajout */}
          <fieldset className="rounded-md border border-dashed app-border p-3">
            <legend className="px-2 text-xs font-semibold uppercase app-text-muted">
              Ajouter une source RSS
            </legend>
            <div className="grid gap-2 sm:grid-cols-2">
              <input type="text" placeholder="Nom court (slug)" value={form.nom}
                     onChange={(e) => setForm({ ...form, nom: e.target.value })}
                     className="rounded border app-border px-2 py-1 text-sm app-surface" />
              <input type="text" placeholder="Libellé affiché" value={form.libelle}
                     onChange={(e) => setForm({ ...form, libelle: e.target.value })}
                     className="rounded border app-border px-2 py-1 text-sm app-surface" />
              <input type="url" placeholder="URL du flux RSS" value={form.url}
                     onChange={(e) => setForm({ ...form, url: e.target.value })}
                     className="col-span-2 rounded border app-border px-2 py-1 text-sm app-surface" />
              <label className="flex items-center gap-2 text-sm">
                <span>Fiabilité :</span>
                <input type="number" min={0} max={1} step={0.05} value={form.fiabilite}
                       onChange={(e) => setForm({ ...form, fiabilite: parseFloat(e.target.value) || 0 })}
                       className="w-20 rounded border app-border px-2 py-1 text-sm app-surface" />
              </label>
              <button type="button" onClick={ajouter}
                      disabled={enCours || !form.nom || !form.libelle || !form.url}
                      className="btn-primary disabled:opacity-50">
                {enCours ? "Ajout…" : "+ Ajouter cette source"}
              </button>
            </div>
            <p className="mt-2 text-xs app-text-muted">
              La source est utilisée au prochain cycle de scraping (toutes les 30 min).
              Seuls les flux RSS sont supportés pour le moment.
            </p>
          </fieldset>
        </div>
      )}
    </div>
  );
}

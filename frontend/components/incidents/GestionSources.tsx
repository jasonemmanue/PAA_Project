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

  // Génère automatiquement un identifiant interne à partir du libellé
  // (minuscules, sans accents, espaces → underscore)
  function slugifier(s: string): string {
    return s
      .toLowerCase()
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .slice(0, 40);
  }

  function messageAmical(status: number, detail: string): string {
    if (status === 422) {
      if (detail.includes("nom")) return "Le nom du site doit contenir au moins 2 caractères.";
      if (detail.includes("libelle")) return "Le nom affiché doit contenir au moins 2 caractères.";
      if (detail.includes("url")) return "L'adresse du flux RSS n'est pas valide (doit commencer par https://).";
      return "Certains champs ne sont pas correctement remplis. Vérifiez le nom et l'adresse.";
    }
    if (status === 409) return "Une source avec ce nom existe déjà.";
    if (status >= 500) return "Le serveur ne répond pas pour le moment. Réessayez dans un instant.";
    return `Erreur (code ${status}). ${detail.slice(0, 200)}`;
  }

  // Catalogue des flux RSS connus pour les sites ivoiriens — évite à
  // l'utilisateur d'avoir à les chercher. Clé = nom de domaine.
  const RSS_CONNUS: Record<string, string> = {
    "fraternitematin.ci": "https://www.fraternitematin.ci/feed/",
    "abidjan.net": "https://news.abidjan.net/rss.php",
    "news.abidjan.net": "https://news.abidjan.net/rss.php",
    "koaci.com": "https://koaci.com/rss.xml",
    "linfodrome.ci": "https://www.linfodrome.ci/feed",
    "soir-info.ci": "https://www.soir-info.ci/feed",
    "rfi.fr": "https://www.rfi.fr/fr/afrique/rss",
    "ivoiresoir.net": "https://www.ivoiresoir.net/feed/",
    "afrik.com": "https://www.afrik.com/feed",
  };

  // Construit une URL RSS valide à partir de ce que l'utilisateur a tapé :
  //  - URL RSS complète → renvoyée telle quelle
  //  - URL d'un site connu → URL RSS du catalogue
  //  - URL d'un site inconnu → on tente d'ajouter /feed/ en suffixe
  function devinerUrlRss(saisie: string): string {
    let s = saisie.trim();
    if (!s) return "";
    if (!s.startsWith("http://") && !s.startsWith("https://")) s = "https://" + s;
    // Déjà un flux RSS
    if (/\/(feed|rss|rss\.xml|feed\.xml)\/?$/i.test(s) || /\.xml$/i.test(s)) return s;
    try {
      const u = new URL(s);
      const host = u.hostname.replace(/^www\./, "");
      if (RSS_CONNUS[host]) return RSS_CONNUS[host];
      if (RSS_CONNUS[u.hostname]) return RSS_CONNUS[u.hostname];
    } catch {
      return s;
    }
    // Repli : appendre /feed/ (convention WordPress, qui couvre la majorité
    // des journaux ivoiriens : Fraternité Matin, L'Infodrome, Soir Info…)
    return s.replace(/\/+$/, "") + "/feed/";
  }

  async function ajouter() {
    setEnCours(true); setErreur(null);
    try {
      const urlRss = devinerUrlRss(form.url);
      const payload = {
        ...form,
        url: urlRss,
        nom: form.nom || slugifier(form.libelle),
      };
      const rep = await fetch(`${API_BASE}/incidents/sources`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!rep.ok) {
        const txt = await rep.text().catch(() => "");
        throw new Error(messageAmical(rep.status, txt));
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
        body: JSON.stringify({ actif: !s.actif }),
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
            <div className="flex items-start justify-between gap-2 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-700 dark:bg-red-950/30 dark:text-red-300">
              <span>{erreur}</span>
              <button
                type="button"
                onClick={() => setErreur(null)}
                className="shrink-0 rounded px-1 font-bold opacity-70 hover:opacity-100"
                title="Fermer ce message"
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

          {/* Formulaire ajout — termes accessibles */}
          <fieldset className="rounded-md border border-dashed app-border p-4">
            <legend className="px-2 text-sm font-semibold app-text-muted">
              ➕ Ajouter un nouveau journal / site d'actualités
            </legend>

            {/* Exemple concret */}
            <div className="mb-4 rounded-md bg-paa-blue-50 dark:bg-paa-navy-800/60 border border-paa-blue-200 dark:border-paa-navy-600 p-3 text-xs">
              <p className="font-semibold text-paa-navy-800 dark:text-paa-blue-100 mb-1">
                💡 Comment remplir — il suffit de l'adresse du site
              </p>
              <ul className="space-y-1 text-paa-navy-700 dark:text-paa-blue-200">
                <li><b>Nom du site</b> : Fraternité Matin</li>
                <li><b>Adresse du site</b> : https://www.fraternitematin.ci</li>
                <li><b>Confiance</b> : 90 %</li>
              </ul>
              <p className="mt-2 italic text-paa-navy-600 dark:text-paa-blue-300">
                Vous pouvez coller l'adresse <b>simple du site</b> — l'application
                ajoutera automatiquement <span className="font-mono">/feed/</span> ou
                trouvera la bonne adresse RSS si le site est connu (Fraternité Matin,
                Abidjan.net, Koaci, L'Infodrome, Soir Info, RFI Afrique, Ivoiresoir,
                Afrik.com…). Sinon, demandez l'adresse RSS à l'<b>Assistant PAA-Traverse</b>
                en bas à droite — il connaît les URLs RSS des journaux ivoiriens.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="flex flex-col gap-1 sm:col-span-2">
                <span className="text-xs font-medium app-text-muted">
                  Nom du site <span className="text-statut-congestionne">*</span>
                </span>
                <input
                  type="text"
                  placeholder="Ex. Fraternité Matin"
                  value={form.libelle}
                  onChange={(e) => setForm({
                    ...form,
                    libelle: e.target.value,
                    nom: slugifier(e.target.value),
                  })}
                  className="rounded border app-border px-3 py-2 text-sm app-surface"
                />
              </label>

              <label className="flex flex-col gap-1 sm:col-span-2">
                <span className="text-xs font-medium app-text-muted">
                  Adresse du site <span className="text-statut-congestionne">*</span>
                </span>
                <input
                  type="url"
                  placeholder="Ex. https://www.fraternitematin.ci"
                  value={form.url}
                  onChange={(e) => setForm({ ...form, url: e.target.value })}
                  className="rounded border app-border px-3 py-2 text-sm app-surface"
                />
                {form.url && (
                  <span className="text-[11px] app-text-muted">
                    Sera enregistré comme :{" "}
                    <span className="font-mono text-paa-blue-600 dark:text-paa-blue-300">
                      {devinerUrlRss(form.url)}
                    </span>
                  </span>
                )}
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium app-text-muted">
                  Confiance dans la source (0 à 100 %)
                </span>
                <div className="flex items-center gap-2">
                  <input
                    type="range"
                    min={0}
                    max={100}
                    step={5}
                    value={Math.round(form.fiabilite * 100)}
                    onChange={(e) => setForm({ ...form, fiabilite: parseInt(e.target.value, 10) / 100 })}
                    className="flex-1"
                  />
                  <span className="w-12 text-right text-sm font-semibold tabular-nums">
                    {Math.round(form.fiabilite * 100)} %
                  </span>
                </div>
              </label>

              <div className="flex items-end">
                <button
                  type="button"
                  onClick={ajouter}
                  disabled={enCours || !form.libelle || form.libelle.length < 2 || !form.url || form.url.length < 5}
                  className="w-full rounded-md bg-paa-blue-500 px-4 py-2 text-sm font-semibold text-white
                             shadow-paa-sm hover:bg-paa-blue-600 transition-colors
                             disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {enCours ? "Ajout en cours…" : "Ajouter ce site"}
                </button>
              </div>
            </div>

            <p className="mt-3 text-xs app-text-muted">
              ℹ️ Le robot ira chercher les nouveaux incidents sur ce site
              <b> toutes les 30 minutes</b>. Vous pouvez désactiver une source à
              tout moment sans la supprimer.
            </p>
          </fieldset>
        </div>
      )}
    </div>
  );
}

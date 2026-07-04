"use client";

/**
 * AutocompleteLieu — champ de saisie avec suggestions Nominatim OSM.
 *
 * Debounce 350 ms côté client, cache mémoire côté backend (1 h), rate limit
 * sortant Nominatim (1 req/s max). Sélection d'une suggestion → callback
 * `onSelect(nom, lat, lon)` qui remplit les champs lat/lon du parent.
 *
 * Cf. CLAUDE.md § 17.3 — Autocomplétion des lieux (P12.3).
 */

import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { SuggestionLieu } from "@/lib/types";

interface Props {
  label: string;
  placeholder?: string;
  couleurBadge?: string; // ex. "#16a34a" pour Début, "#dc2626" pour Fin
  valeurInitiale?: string;
  onSelect: (nom: string, lat: number, lon: number) => void;
  onEffacer?: () => void;
}

const DEBOUNCE_MS = 350;
const LONGUEUR_MIN = 3;

export function AutocompleteLieu({
  label,
  placeholder = "Ex. Pharmacie Palm Beach, Pont Houphouët-Boigny…",
  couleurBadge,
  valeurInitiale = "",
  onSelect,
  onEffacer,
}: Props) {
  const [texte, setTexte] = useState<string>(valeurInitiale);
  const [suggestions, setSuggestions] = useState<SuggestionLieu[]>([]);
  const [ouvert, setOuvert] = useState<boolean>(false);
  const [charge, setCharge] = useState<boolean>(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [selectionne, setSelectionne] = useState<boolean>(false);

  const conteneurRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const derniereRequeteRef = useRef<string>("");

  useEffect(() => {
    // Ferme le dropdown au clic extérieur
    const gerer = (e: MouseEvent) => {
      if (!conteneurRef.current) return;
      if (!conteneurRef.current.contains(e.target as Node)) {
        setOuvert(false);
      }
    };
    document.addEventListener("mousedown", gerer);
    return () => document.removeEventListener("mousedown", gerer);
  }, []);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (selectionne) return; // ne pas re-chercher après une sélection

    const q = texte.trim();
    if (q.length < LONGUEUR_MIN) {
      setSuggestions([]);
      setErreur(null);
      return;
    }

    timerRef.current = setTimeout(async () => {
      derniereRequeteRef.current = q;
      setCharge(true);
      setErreur(null);
      try {
        const rep = await api.geocoderLieu(q, 5);
        // Discard si une autre requête a été lancée entre-temps
        if (derniereRequeteRef.current !== q) return;
        if (rep.erreur) {
          setErreur(rep.erreur);
          setSuggestions([]);
        } else {
          setSuggestions(rep.resultats);
          setOuvert(rep.resultats.length > 0);
        }
      } catch (e) {
        if (derniereRequeteRef.current !== q) return;
        setErreur(e instanceof Error ? e.message : "Erreur de recherche.");
        setSuggestions([]);
      } finally {
        if (derniereRequeteRef.current === q) setCharge(false);
      }
    }, DEBOUNCE_MS);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [texte, selectionne]);

  const choisir = (s: SuggestionLieu) => {
    setTexte(s.nom_affiche);
    setSelectionne(true);
    setOuvert(false);
    setSuggestions([]);
    onSelect(s.nom_affiche, s.lat, s.lon);
  };

  const surSaisie = (v: string) => {
    setTexte(v);
    setSelectionne(false);
    if (v.trim().length < LONGUEUR_MIN && onEffacer) onEffacer();
  };

  return (
    <div ref={conteneurRef} className="relative flex flex-col gap-1">
      <label className="text-fluid-sm font-medium flex items-center gap-2">
        {couleurBadge && (
          <span
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: couleurBadge }}
            aria-hidden="true"
          />
        )}
        {label}
      </label>
      <div className="relative">
        <input
          type="text"
          value={texte}
          onChange={(e) => surSaisie(e.target.value)}
          onFocus={() => suggestions.length > 0 && setOuvert(true)}
          placeholder={placeholder}
          autoComplete="off"
          className="w-full rounded-md border app-border app-surface px-3 py-2 pr-9 text-fluid-base
                     focus:outline-none focus:ring-2 focus:ring-paa-blue-400 min-h-[42px]"
        />
        {charge && (
          <span
            className="absolute right-3 top-1/2 -translate-y-1/2 text-fluid-xs app-text-muted"
            aria-label="Recherche en cours"
          >
            ⏳
          </span>
        )}
        {!charge && selectionne && (
          <span
            className="absolute right-3 top-1/2 -translate-y-1/2 text-statut-fluide"
            aria-label="Sélectionné"
          >
            ✓
          </span>
        )}
      </div>
      {ouvert && suggestions.length > 0 && (
        <ul
          className="absolute top-full left-0 right-0 z-40 mt-1 max-h-72 overflow-y-auto rounded-md
                     border app-border bg-white shadow-lg dark:bg-paa-navy-900"
          role="listbox"
        >
          {suggestions.map((s, i) => (
            <li key={`${s.lat}-${s.lon}-${i}`}>
              <button
                type="button"
                onClick={() => choisir(s)}
                className="w-full text-left px-3 py-2 text-fluid-xs
                           hover:bg-paa-blue-50 dark:hover:bg-paa-navy-800
                           focus:outline-none focus:bg-paa-blue-50 dark:focus:bg-paa-navy-800"
                role="option"
              >
                <div className="font-medium truncate">{s.nom_affiche}</div>
                <div className="app-text-muted font-mono text-[10px] mt-0.5">
                  {s.lat.toFixed(5)}, {s.lon.toFixed(5)} · {s.type}
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
      {erreur && !ouvert && (
        <p className="text-fluid-xs text-statut-congestionne">{erreur}</p>
      )}
      {texte.trim().length >= LONGUEUR_MIN && !charge && !ouvert && suggestions.length === 0 && !erreur && !selectionne && (
        <p className="text-fluid-xs app-text-muted">
          Aucun lieu trouvé. Essayez un nom plus court ou plus précis (ex. « CARENA », « Palm Beach »).
        </p>
      )}
    </div>
  );
}

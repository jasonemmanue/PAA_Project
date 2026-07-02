"use client";

import { useState } from "react";
import { usePlageHoraire } from "@/contexts/PlageHoraireContext";

const HEURES = Array.from({ length: 25 }, (_, i) => i);

export function SelecteurPlageHoraire() {
  const { heureDebut, heureFin, setPlage, est24h } = usePlageHoraire();
  const [ouvert, setOuvert] = useState(false);
  const [dLocal, setDLocal] = useState(heureDebut);
  const [fLocal, setFLocal] = useState(heureFin);

  const ouvrir = () => {
    setDLocal(heureDebut);
    setFLocal(heureFin);
    setOuvert(true);
  };

  const appliquer = () => {
    if (dLocal < fLocal) {
      setPlage(dLocal, fLocal);
    }
    setOuvert(false);
  };

  const reinitialiser = () => {
    setDLocal(0);
    setFLocal(24);
    setPlage(0, 24);
    setOuvert(false);
  };

  const label = est24h
    ? "24h/24"
    : `${String(heureDebut).padStart(2, "0")}h–${String(heureFin).padStart(2, "0")}h`;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={ouvrir}
        className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[11px] font-medium
                    transition-colors border
                    ${est24h
                      ? "border-white/20 text-paa-blue-100 hover:bg-white/10"
                      : "border-amber-400/60 bg-amber-500/20 text-amber-200 hover:bg-amber-500/30"
                    }`}
        title="Filtrer par plage horaire"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm.75-13a.75.75 0 00-1.5 0v5c0 .414.336.75.75.75h4a.75.75 0 000-1.5h-3.25V5z" clipRule="evenodd" />
        </svg>
        <span className="hidden sm:inline">{label}</span>
      </button>

      {ouvert && (
        <>
          <div className="fixed inset-0 z-[1200]" onClick={() => setOuvert(false)} />
          <div className="absolute right-0 top-full mt-2 z-[1201] w-[260px]
                          rounded-lg border border-paa-blue-200 dark:border-paa-navy-700
                          bg-white dark:bg-paa-navy-900 shadow-xl p-4">
            <h3 className="text-[12px] font-semibold text-paa-navy-800 dark:text-paa-blue-100 mb-3">
              Plage horaire d'analyse
            </h3>

            <div className="flex items-center gap-2 mb-3">
              <div className="flex-1">
                <label className="block text-[10px] text-gray-500 dark:text-gray-400 mb-1 uppercase tracking-wider">
                  Début
                </label>
                <select
                  value={dLocal}
                  onChange={(e) => setDLocal(Number(e.target.value))}
                  className="w-full rounded-md border border-gray-300 dark:border-paa-navy-600
                             bg-white dark:bg-paa-navy-800 px-2 py-1.5 text-[12px]
                             text-paa-navy-900 dark:text-paa-blue-100
                             focus:outline-none focus:ring-2 focus:ring-paa-blue-400"
                >
                  {HEURES.filter((h) => h < 24).map((h) => (
                    <option key={h} value={h}>
                      {String(h).padStart(2, "0")}h00
                    </option>
                  ))}
                </select>
              </div>

              <span className="text-gray-400 dark:text-gray-500 mt-4 text-sm font-bold">→</span>

              <div className="flex-1">
                <label className="block text-[10px] text-gray-500 dark:text-gray-400 mb-1 uppercase tracking-wider">
                  Fin
                </label>
                <select
                  value={fLocal}
                  onChange={(e) => setFLocal(Number(e.target.value))}
                  className="w-full rounded-md border border-gray-300 dark:border-paa-navy-600
                             bg-white dark:bg-paa-navy-800 px-2 py-1.5 text-[12px]
                             text-paa-navy-900 dark:text-paa-blue-100
                             focus:outline-none focus:ring-2 focus:ring-paa-blue-400"
                >
                  {HEURES.filter((h) => h >= 1 && h > dLocal).map((h) => (
                    <option key={h} value={h}>
                      {String(h).padStart(2, "0")}h00
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {dLocal >= fLocal && (
              <p className="text-[10px] text-red-500 mb-2">
                L'heure de fin doit être supérieure à l'heure de début.
              </p>
            )}

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={appliquer}
                disabled={dLocal >= fLocal}
                className="flex-1 rounded-md bg-paa-blue-600 px-3 py-1.5 text-[11px] font-medium
                           text-white hover:bg-paa-blue-700 disabled:opacity-40 transition-colors"
              >
                Appliquer
              </button>
              <button
                type="button"
                onClick={reinitialiser}
                className="rounded-md border border-gray-300 dark:border-paa-navy-600
                           px-3 py-1.5 text-[11px] font-medium
                           text-gray-600 dark:text-gray-300
                           hover:bg-gray-50 dark:hover:bg-paa-navy-800 transition-colors"
              >
                24h/24
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

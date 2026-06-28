"use client";

import { useEffect, useState } from "react";

import type { NiveauAcces } from "@/contexts/AuthContext";

const CLE_MDP_LECTURE = "paa_mdp_lecture";
const CLE_MDP_ECRITURE = "paa_mdp_ecriture";
const MDP_LECTURE_DEFAUT = "readhackatonia";
const MDP_ECRITURE_DEFAUT = "readwritehackatonia";

function getMdpLecture(): string {
  if (typeof window === "undefined") return MDP_LECTURE_DEFAUT;
  return localStorage.getItem(CLE_MDP_LECTURE) ?? MDP_LECTURE_DEFAUT;
}
function getMdpEcriture(): string {
  if (typeof window === "undefined") return MDP_ECRITURE_DEFAUT;
  return localStorage.getItem(CLE_MDP_ECRITURE) ?? MDP_ECRITURE_DEFAUT;
}

interface Props {
  onAuthentifie: (niveau: NiveauAcces) => void;
}

export function PasswordGate({ onAuthentifie }: Props) {
  const [motDePasse, setMotDePasse] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [modifierMdp, setModifierMdp] = useState(false);
  const [typeChangement, setTypeChangement] = useState<"lecture" | "ecriture">("lecture");
  const [ancienMdp, setAncienMdp] = useState("");
  const [nouveauMdp, setNouveauMdp] = useState("");
  const [messageSucces, setMessageSucces] = useState<string | null>(null);
  const [montre, setMontre] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setMontre(true), 50);
    return () => clearTimeout(t);
  }, []);

  function valider() {
    const mdpL = getMdpLecture();
    const mdpE = getMdpEcriture();
    if (motDePasse === mdpE) {
      onAuthentifie("ecriture");
    } else if (motDePasse === mdpL) {
      onAuthentifie("lecture");
    } else {
      setErreur("Mot de passe incorrect. Veuillez réessayer.");
      setMotDePasse("");
    }
  }

  function changerMotDePasse() {
    const mdpActuel = typeChangement === "lecture" ? getMdpLecture() : getMdpEcriture();
    if (ancienMdp !== mdpActuel) {
      setErreur("Ancien mot de passe incorrect.");
      return;
    }
    if (nouveauMdp.length < 6) {
      setErreur("Le nouveau mot de passe doit comporter au moins 6 caractères.");
      return;
    }
    const cle = typeChangement === "lecture" ? CLE_MDP_LECTURE : CLE_MDP_ECRITURE;
    localStorage.setItem(cle, nouveauMdp);
    setMessageSucces(
      `Mot de passe ${typeChangement === "lecture" ? "lecture" : "lecture/écriture"} mis à jour.`,
    );
    setAncienMdp("");
    setNouveauMdp("");
    setErreur(null);
  }

  return (
    /* Fond plein écran — clair : gris très doux / sombre : marine profond */
    <div
      className={`fixed inset-0 z-[10000] flex flex-col items-center justify-center p-4
                  bg-slate-100 dark:bg-[#070F1E]
                  transition-opacity duration-400 ${montre ? "opacity-100" : "opacity-0"}`}
    >
      {/* Halos décoratifs */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-32 left-1/2 -translate-x-1/2 w-[600px] h-[400px]
                        rounded-full bg-paa-blue-200/30 blur-3xl dark:bg-paa-blue-900/20" />
      </div>

      {/* Carte centrale */}
      <div className="relative w-full max-w-sm rounded-2xl shadow-xl
                      bg-white border border-slate-200
                      dark:bg-paa-navy-800/80 dark:border-paa-navy-600/50
                      dark:backdrop-blur-md p-8">

        {/* Logo + titre */}
        <div className="flex flex-col items-center gap-2 mb-7">
          <div className="flex items-center justify-center w-14 h-14 rounded-full
                          bg-paa-blue-100 dark:bg-paa-blue-900/40">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"
                 className="w-7 h-7 text-paa-blue-600 dark:text-paa-blue-300">
              <path fillRule="evenodd"
                d="M12 1.5a5.25 5.25 0 0 0-5.25 5.25v3a3 3 0 0 0-3 3v6.75a3 3 0 0 0 3
                   3h10.5a3 3 0 0 0 3-3v-6.75a3 3 0 0 0-3-3v-3c0-2.9-2.35-5.25-5.25-5.25Zm3.75
                   8.25v-3a3.75 3.75 0 1 0-7.5 0v3h7.5Z"
                clipRule="evenodd" />
            </svg>
          </div>
          <h1 className="text-xl font-bold text-paa-navy-900 dark:text-paa-blue-100">
            PAA-Traverse
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Port Autonome d&apos;Abidjan — Team HACKATONIA
          </p>
        </div>

        {!modifierMdp ? (
          <>
            <label className="block text-xs font-semibold uppercase tracking-widest
                              text-slate-500 dark:text-slate-400 mb-1.5">
              Mot de passe d&apos;accès
            </label>
            <input
              type="password"
              value={motDePasse}
              onChange={(e) => { setMotDePasse(e.target.value); setErreur(null); }}
              onKeyDown={(e) => e.key === "Enter" && valider()}
              placeholder="••••••••••••"
              autoFocus
              className="w-full px-4 py-2.5 rounded-lg text-base
                         border border-slate-300 bg-white text-slate-900 placeholder-slate-400
                         dark:border-paa-navy-500 dark:bg-paa-navy-900/60 dark:text-slate-100 dark:placeholder-slate-500
                         focus:outline-none focus:ring-2 focus:ring-paa-blue-400
                         mb-3 transition"
            />

            {erreur && (
              <p className="text-sm text-red-600 dark:text-red-400 mb-3">{erreur}</p>
            )}

            <button
              onClick={valider}
              className="w-full py-2.5 rounded-lg font-semibold text-base
                         bg-paa-blue-600 hover:bg-paa-blue-700 text-white
                         dark:bg-paa-blue-500 dark:hover:bg-paa-blue-600
                         transition mb-2.5 focus:outline-none focus:ring-2 focus:ring-paa-blue-400"
            >
              Accéder →
            </button>

            <button
              onClick={() => { setModifierMdp(true); setErreur(null); setMessageSucces(null); }}
              className="w-full py-2 rounded-lg text-sm font-medium
                         text-slate-500 hover:text-slate-700 hover:bg-slate-100
                         dark:text-slate-400 dark:hover:text-slate-200 dark:hover:bg-paa-navy-700
                         border border-slate-200 dark:border-paa-navy-600
                         transition"
            >
              Modifier un mot de passe
            </button>

            {/* Légende niveaux */}
            <div className="mt-5 pt-4 border-t border-slate-200 dark:border-paa-navy-600 flex flex-col gap-1.5">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-paa-blue-500 shrink-0" />
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  <strong className="text-slate-700 dark:text-slate-300">Lecture</strong> — consultation uniquement
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  <strong className="text-slate-700 dark:text-slate-300">Lecture/Écriture</strong> — imports, exports, administration
                </span>
              </div>
            </div>
          </>
        ) : (
          <>
            <p className="text-xs font-semibold uppercase tracking-widest
                          text-slate-500 dark:text-slate-400 mb-3">
              Modifier le mot de passe
            </p>

            {/* Sélecteur type */}
            <div className="flex gap-2 mb-4">
              {(["lecture", "ecriture"] as const).map((type) => (
                <button
                  key={type}
                  onClick={() => setTypeChangement(type)}
                  className={`flex-1 py-1.5 rounded-md text-sm font-medium transition
                    ${typeChangement === type
                      ? "bg-paa-blue-600 text-white dark:bg-paa-blue-500"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-paa-navy-700 dark:text-slate-300 dark:hover:bg-paa-navy-600"
                    }`}
                >
                  {type === "lecture" ? "Lecture" : "Lecture/Écriture"}
                </button>
              ))}
            </div>

            <input
              type="password"
              value={ancienMdp}
              onChange={(e) => { setAncienMdp(e.target.value); setErreur(null); }}
              placeholder="Ancien mot de passe"
              className="w-full px-4 py-2.5 rounded-lg text-sm mb-2
                         border border-slate-300 bg-white text-slate-900 placeholder-slate-400
                         dark:border-paa-navy-500 dark:bg-paa-navy-900/60 dark:text-slate-100 dark:placeholder-slate-500
                         focus:outline-none focus:ring-2 focus:ring-paa-blue-400 transition"
            />
            <input
              type="password"
              value={nouveauMdp}
              onChange={(e) => { setNouveauMdp(e.target.value); setErreur(null); }}
              placeholder="Nouveau mot de passe (min. 6 car.)"
              className="w-full px-4 py-2.5 rounded-lg text-sm mb-3
                         border border-slate-300 bg-white text-slate-900 placeholder-slate-400
                         dark:border-paa-navy-500 dark:bg-paa-navy-900/60 dark:text-slate-100 dark:placeholder-slate-500
                         focus:outline-none focus:ring-2 focus:ring-paa-blue-400 transition"
            />

            {erreur && (
              <p className="text-sm text-red-600 dark:text-red-400 mb-2">{erreur}</p>
            )}
            {messageSucces && (
              <p className="text-sm text-emerald-600 dark:text-emerald-400 mb-2">{messageSucces}</p>
            )}

            <button
              onClick={changerMotDePasse}
              className="w-full py-2.5 rounded-lg font-semibold text-sm
                         bg-paa-blue-600 hover:bg-paa-blue-700 text-white
                         dark:bg-paa-blue-500 dark:hover:bg-paa-blue-600
                         transition mb-2 focus:outline-none focus:ring-2 focus:ring-paa-blue-400"
            >
              Mettre à jour
            </button>
            <button
              onClick={() => {
                setModifierMdp(false);
                setErreur(null);
                setMessageSucces(null);
                setAncienMdp("");
                setNouveauMdp("");
              }}
              className="w-full py-2 rounded-lg text-sm font-medium
                         text-slate-500 hover:text-slate-700 hover:bg-slate-100
                         dark:text-slate-400 dark:hover:text-slate-200 dark:hover:bg-paa-navy-700
                         border border-slate-200 dark:border-paa-navy-600 transition"
            >
              ← Retour
            </button>
          </>
        )}
      </div>
    </div>
  );
}

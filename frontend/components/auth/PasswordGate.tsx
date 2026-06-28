"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import Image from "next/image";

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

/** Icône soleil (mode clair) */
function IconSoleil({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M12 2.25a.75.75 0 0 1 .75.75v2.25a.75.75 0 0 1-1.5 0V3a.75.75 0 0 1 .75-.75ZM7.5 12a4.5 4.5 0 1 1 9 0 4.5 4.5 0 0 1-9 0ZM18.894 6.166a.75.75 0 0 0-1.06-1.06l-1.591 1.59a.75.75 0 1 0 1.06 1.061l1.591-1.59ZM21.75 12a.75.75 0 0 1-.75.75h-2.25a.75.75 0 0 1 0-1.5H21a.75.75 0 0 1 .75.75ZM17.834 18.894a.75.75 0 0 0 1.06-1.06l-1.59-1.591a.75.75 0 1 0-1.061 1.06l1.59 1.591ZM12 18a.75.75 0 0 1 .75.75V21a.75.75 0 0 1-1.5 0v-2.25A.75.75 0 0 1 12 18ZM7.758 17.303a.75.75 0 0 0-1.061-1.06l-1.591 1.59a.75.75 0 0 0 1.06 1.061l1.591-1.59ZM6 12a.75.75 0 0 1-.75.75H3a.75.75 0 0 1 0-1.5h2.25A.75.75 0 0 1 6 12ZM6.697 7.757a.75.75 0 0 0 1.06-1.06l-1.59-1.591a.75.75 0 0 0-1.061 1.06l1.59 1.591Z" />
    </svg>
  );
}

/** Icône lune (mode sombre) */
function IconLune({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path fillRule="evenodd" d="M9.528 1.718a.75.75 0 0 1 .162.819A8.97 8.97 0 0 0 9 6a9 9 0 0 0 9 9 8.97 8.97 0 0 0 3.463-.69.75.75 0 0 1 .981.98 10.503 10.503 0 0 1-9.694 6.46c-5.799 0-10.5-4.7-10.5-10.5 0-4.368 2.667-8.112 6.46-9.694a.75.75 0 0 1 .818.162Z" clipRule="evenodd" />
    </svg>
  );
}

/** Bouton de bascule thème clair ↔ sombre */
function BoutonTheme() {
  const { resolvedTheme, setTheme } = useTheme();
  const [monte, setMonte] = useState(false);
  useEffect(() => setMonte(true), []);
  if (!monte) return null;

  const estSombre = resolvedTheme === "dark";
  return (
    <button
      onClick={() => setTheme(estSombre ? "light" : "dark")}
      title={estSombre ? "Passer en mode clair" : "Passer en mode sombre"}
      className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium
                 bg-white/70 hover:bg-white text-slate-700 border border-slate-200
                 dark:bg-slate-800/70 dark:hover:bg-slate-700 dark:text-slate-200 dark:border-slate-600
                 backdrop-blur-sm transition-all shadow-sm"
    >
      {estSombre
        ? <><IconSoleil className="w-3.5 h-3.5" /> Clair</>
        : <><IconLune className="w-3.5 h-3.5" /> Sombre</>}
    </button>
  );
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

  /* Classes communes aux inputs */
  const inputCls =
    "w-full px-4 py-2.5 rounded-lg text-sm " +
    "border border-slate-300 bg-white text-slate-900 placeholder-slate-400 " +
    "dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:placeholder-slate-500 " +
    "focus:outline-none focus:ring-2 focus:ring-blue-500 transition";

  return (
    <div
      className={`fixed inset-0 z-[10000] flex flex-col items-center justify-center p-4
                  transition-opacity duration-500 ${montre ? "opacity-100" : "opacity-0"}
                  bg-slate-100 dark:bg-slate-950`}
    >
      {/* ── Filigrane logo PAA ── */}
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center overflow-hidden">
        <Image
          src="/logo-hackathon.jpg"
          alt=""
          width={520}
          height={347}
          className="select-none opacity-[0.07] dark:opacity-[0.05] grayscale"
          priority
        />
      </div>

      {/* ── Barre supérieure : toggle thème ── */}
      <div className="absolute top-4 right-4 flex items-center gap-2">
        <BoutonTheme />
      </div>

      {/* ── Carte centrale ── */}
      <div className="relative w-full max-w-sm rounded-2xl shadow-xl ring-1
                      bg-white ring-slate-200
                      dark:bg-slate-900 dark:ring-slate-700
                      p-8">

        {/* Logo + titre */}
        <div className="flex flex-col items-center gap-3 mb-7">
          <div className="relative w-16 h-16 rounded-full overflow-hidden shadow ring-2 ring-slate-200 dark:ring-slate-600">
            <Image
              src="/logo-hackathon.jpg"
              alt="Logo Port Autonome d'Abidjan"
              fill
              className="object-cover"
              sizes="64px"
            />
          </div>
          <div className="text-center">
            <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">
              PAA-Traverse
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Port Autonome d&apos;Abidjan — Team HACKATONIA
            </p>
          </div>
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
              className={`${inputCls} mb-3`}
            />

            {erreur && (
              <p className="text-sm text-red-600 dark:text-red-400 mb-3">{erreur}</p>
            )}

            <button
              onClick={valider}
              className="w-full py-2.5 rounded-lg font-semibold text-base
                         bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white
                         transition mb-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
                         dark:focus:ring-offset-slate-900 shadow-md"
            >
              Accéder →
            </button>

            <button
              onClick={() => { setModifierMdp(true); setErreur(null); setMessageSucces(null); }}
              className="w-full py-2 rounded-lg text-sm font-medium
                         text-slate-500 hover:text-slate-700 hover:bg-slate-100
                         dark:text-slate-400 dark:hover:text-slate-200 dark:hover:bg-slate-800
                         border border-slate-200 dark:border-slate-700
                         transition"
            >
              Modifier un mot de passe
            </button>

            {/* Légende niveaux */}
            <div className="mt-5 pt-4 border-t border-slate-200 dark:border-slate-700 flex flex-col gap-1.5">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-blue-500 shrink-0" />
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
                      ? "bg-blue-600 text-white shadow"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
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
              className={`${inputCls} mb-2`}
            />
            <input
              type="password"
              value={nouveauMdp}
              onChange={(e) => { setNouveauMdp(e.target.value); setErreur(null); }}
              placeholder="Nouveau mot de passe (min. 6 car.)"
              className={`${inputCls} mb-3`}
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
                         bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white
                         transition mb-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
                         dark:focus:ring-offset-slate-900 shadow-md"
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
                         dark:text-slate-400 dark:hover:text-slate-200 dark:hover:bg-slate-800
                         border border-slate-200 dark:border-slate-700 transition"
            >
              ← Retour
            </button>
          </>
        )}
      </div>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import Image from "next/image";

import type { NiveauAcces } from "@/contexts/AuthContext";

const CLE_MDP_LECTURE  = "paa_mdp_lecture";
const CLE_MDP_ECRITURE = "paa_mdp_ecriture";
const MDP_LECTURE_DEFAUT  = "readhackatonia";
const MDP_ECRITURE_DEFAUT = "readwritehackatonia";

function getMdpLecture():  string {
  if (typeof window === "undefined") return MDP_LECTURE_DEFAUT;
  return localStorage.getItem(CLE_MDP_LECTURE)  ?? MDP_LECTURE_DEFAUT;
}
function getMdpEcriture(): string {
  if (typeof window === "undefined") return MDP_ECRITURE_DEFAUT;
  return localStorage.getItem(CLE_MDP_ECRITURE) ?? MDP_ECRITURE_DEFAUT;
}

interface Props { onAuthentifie: (n: NiveauAcces) => void }

/* ─── Icônes ─────────────────────────────────────────────────────────────── */
function Soleil({ cls }: { cls?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className={cls}>
      <path d="M12 2.25a.75.75 0 0 1 .75.75v2.25a.75.75 0 0 1-1.5 0V3a.75.75 0 0 1 .75-.75ZM7.5 12a4.5 4.5 0 1 1 9 0 4.5 4.5 0 0 1-9 0ZM18.894 6.166a.75.75 0 0 0-1.06-1.06l-1.591 1.59a.75.75 0 1 0 1.06 1.061l1.591-1.59ZM21.75 12a.75.75 0 0 1-.75.75h-2.25a.75.75 0 0 1 0-1.5H21a.75.75 0 0 1 .75.75ZM17.834 18.894a.75.75 0 0 0 1.06-1.06l-1.59-1.591a.75.75 0 1 0-1.061 1.06l1.59 1.591ZM12 18a.75.75 0 0 1 .75.75V21a.75.75 0 0 1-1.5 0v-2.25A.75.75 0 0 1 12 18ZM7.758 17.303a.75.75 0 0 0-1.061-1.06l-1.591 1.59a.75.75 0 0 0 1.06 1.061l1.591-1.59ZM6 12a.75.75 0 0 1-.75.75H3a.75.75 0 0 1 0-1.5h2.25A.75.75 0 0 1 6 12ZM6.697 7.757a.75.75 0 0 0 1.06-1.06l-1.59-1.591a.75.75 0 0 0-1.061 1.06l1.59 1.591Z" />
    </svg>
  );
}
function Lune({ cls }: { cls?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className={cls}>
      <path fillRule="evenodd" d="M9.528 1.718a.75.75 0 0 1 .162.819A8.97 8.97 0 0 0 9 6a9 9 0 0 0 9 9 8.97 8.97 0 0 0 3.463-.69.75.75 0 0 1 .981.98 10.503 10.503 0 0 1-9.694 6.46c-5.799 0-10.5-4.7-10.5-10.5 0-4.368 2.667-8.112 6.46-9.694a.75.75 0 0 1 .818.162Z" clipRule="evenodd" />
    </svg>
  );
}

function BoutonTheme() {
  const { resolvedTheme, setTheme } = useTheme();
  const [monte, setMonte] = useState(false);
  useEffect(() => setMonte(true), []);
  if (!monte) return null;
  const sombre = resolvedTheme === "dark";
  return (
    <button
      onClick={() => setTheme(sombre ? "light" : "dark")}
      title={sombre ? "Mode clair" : "Mode sombre"}
      className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold
                 bg-white/80 hover:bg-white text-slate-700 border border-slate-200 shadow-sm
                 dark:bg-slate-800/80 dark:hover:bg-slate-700 dark:text-slate-200 dark:border-slate-600
                 backdrop-blur-sm transition-all"
    >
      {sombre ? <><Soleil cls="w-3.5 h-3.5" /> Clair</> : <><Lune cls="w-3.5 h-3.5" /> Sombre</>}
    </button>
  );
}

/* ─── Composant principal ─────────────────────────────────────────────────── */
export function PasswordGate({ onAuthentifie }: Props) {
  const [mdp,      setMdp]      = useState("");
  const [erreur,   setErreur]   = useState<string | null>(null);
  const [changer,  setChanger]  = useState(false);
  const [typeMdp,  setTypeMdp]  = useState<"lecture" | "ecriture">("lecture");
  const [ancien,   setAncien]   = useState("");
  const [nouveau,  setNouveau]  = useState("");
  const [succes,   setSucces]   = useState<string | null>(null);
  const [montre,   setMontre]   = useState(false);

  useEffect(() => { const t = setTimeout(() => setMontre(true), 50); return () => clearTimeout(t); }, []);

  function valider() {
    if (mdp === getMdpEcriture()) { onAuthentifie("ecriture"); return; }
    if (mdp === getMdpLecture())  { onAuthentifie("lecture");  return; }
    setErreur("Mot de passe incorrect. Veuillez réessayer.");
    setMdp("");
  }

  function changerMdp() {
    const actuel = typeMdp === "lecture" ? getMdpLecture() : getMdpEcriture();
    if (ancien !== actuel) { setErreur("Ancien mot de passe incorrect."); return; }
    if (nouveau.length < 6) { setErreur("Au moins 6 caractères requis."); return; }
    localStorage.setItem(typeMdp === "lecture" ? CLE_MDP_LECTURE : CLE_MDP_ECRITURE, nouveau);
    setSucces(`Mot de passe ${typeMdp === "lecture" ? "lecture" : "lecture/écriture"} mis à jour.`);
    setAncien(""); setNouveau(""); setErreur(null);
  }

  const inputCls =
    "w-full px-4 py-2.5 rounded-lg text-sm border transition " +
    "border-slate-300 bg-white text-slate-900 placeholder-slate-400 " +
    "dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:placeholder-slate-500 " +
    "focus:outline-none focus:ring-2 focus:ring-blue-500";

  return (
    <div
      className={`fixed inset-0 z-[10000] flex flex-col
                  transition-opacity duration-500 ${montre ? "opacity-100" : "opacity-0"}
                  bg-gradient-to-br from-slate-100 via-blue-50 to-slate-200
                  dark:from-slate-950 dark:via-slate-900 dark:to-slate-950`}
    >
      {/* ── Toggle thème (coin haut-droit) ── */}
      <div className="absolute top-4 right-4 z-10">
        <BoutonTheme />
      </div>

      {/* ── Contenu central : 3 colonnes sur desktop ── */}
      <div className="flex flex-1 items-center justify-center px-4 py-8 gap-8 lg:gap-16">

        {/* ── Colonne gauche : logo PAA ── */}
        <div className="hidden lg:flex flex-col items-center gap-4 shrink-0">
          <div className="relative w-52 h-52 rounded-full overflow-hidden
                          shadow-2xl ring-4 ring-white dark:ring-slate-700
                          bg-white dark:bg-slate-800">
            <Image
              src="/logo-hackathon.jpg"
              alt="Port Autonome d'Abidjan"
              fill
              className="object-cover"
              sizes="208px"
              priority
            />
          </div>
          <div className="text-center">
            <p className="text-sm font-semibold text-slate-700 dark:text-slate-300 tracking-wide">
              PORT AUTONOME
            </p>
            <p className="text-sm font-semibold text-slate-700 dark:text-slate-300 tracking-wide">
              D&apos;ABIDJAN
            </p>
          </div>
        </div>

        {/* ── Colonne centrale : carte de connexion ── */}
        <div className="w-full max-w-sm shrink-0">

          {/* Logo visible uniquement sur mobile (au-dessus de la carte) */}
          <div className="flex lg:hidden justify-center mb-5">
            <div className="relative w-20 h-20 rounded-full overflow-hidden shadow-lg ring-2 ring-white dark:ring-slate-600">
              <Image src="/logo-hackathon.jpg" alt="PAA" fill className="object-cover" sizes="80px" priority />
            </div>
          </div>

          <div className="rounded-2xl shadow-xl ring-1
                          bg-white ring-slate-200
                          dark:bg-slate-900 dark:ring-slate-700
                          p-8">
            {/* Titre */}
            <div className="text-center mb-7">
              <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
                FLUIDIS
              </h1>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Accès sécurisé — entrez votre mot de passe
              </p>
            </div>

            {!changer ? (
              <>
                <label className="block text-xs font-semibold uppercase tracking-widest
                                  text-slate-500 dark:text-slate-400 mb-1.5">
                  Mot de passe d&apos;accès
                </label>
                <input
                  type="password"
                  value={mdp}
                  onChange={(e) => { setMdp(e.target.value); setErreur(null); }}
                  onKeyDown={(e) => e.key === "Enter" && valider()}
                  placeholder="••••••••••••"
                  autoFocus
                  className={`${inputCls} mb-3`}
                />

                {erreur && <p className="text-sm text-red-600 dark:text-red-400 mb-3">{erreur}</p>}

                <button
                  onClick={valider}
                  className="w-full py-3 rounded-lg font-bold text-base text-white
                             bg-blue-600 hover:bg-blue-700 active:bg-blue-800
                             shadow-md hover:shadow-lg transition-all
                             focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
                             dark:focus:ring-offset-slate-900 mb-2.5"
                >
                  Accéder →
                </button>

                <button
                  onClick={() => { setChanger(true); setErreur(null); setSucces(null); }}
                  className="w-full py-2 rounded-lg text-sm font-medium
                             text-slate-500 hover:text-slate-700 hover:bg-slate-100
                             dark:text-slate-400 dark:hover:text-slate-200 dark:hover:bg-slate-800
                             border border-slate-200 dark:border-slate-700 transition"
                >
                  Modifier un mot de passe
                </button>

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
                <div className="flex gap-2 mb-4">
                  {(["lecture", "ecriture"] as const).map((t) => (
                    <button
                      key={t}
                      onClick={() => setTypeMdp(t)}
                      className={`flex-1 py-1.5 rounded-md text-sm font-medium transition
                        ${typeMdp === t
                          ? "bg-blue-600 text-white shadow"
                          : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
                        }`}
                    >
                      {t === "lecture" ? "Lecture" : "Lecture/Écriture"}
                    </button>
                  ))}
                </div>
                <input type="password" value={ancien}  onChange={(e) => { setAncien(e.target.value);  setErreur(null); }} placeholder="Ancien mot de passe"              className={`${inputCls} mb-2`} />
                <input type="password" value={nouveau} onChange={(e) => { setNouveau(e.target.value); setErreur(null); }} placeholder="Nouveau mot de passe (min. 6 car.)" className={`${inputCls} mb-3`} />
                {erreur && <p className="text-sm text-red-600 dark:text-red-400 mb-2">{erreur}</p>}
                {succes && <p className="text-sm text-emerald-600 dark:text-emerald-400 mb-2">{succes}</p>}
                <button onClick={changerMdp}
                  className="w-full py-2.5 rounded-lg font-semibold text-sm text-white
                             bg-blue-600 hover:bg-blue-700 shadow-md transition mb-2
                             focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
                             dark:focus:ring-offset-slate-900">
                  Mettre à jour
                </button>
                <button onClick={() => { setChanger(false); setErreur(null); setSucces(null); setAncien(""); setNouveau(""); }}
                  className="w-full py-2 rounded-lg text-sm font-medium
                             text-slate-500 hover:text-slate-700 hover:bg-slate-100
                             dark:text-slate-400 dark:hover:text-slate-200 dark:hover:bg-slate-800
                             border border-slate-200 dark:border-slate-700 transition">
                  ← Retour
                </button>
              </>
            )}
          </div>
        </div>

        {/* ── Colonne droite : HACKATONIA ── */}
        <div className="hidden lg:flex flex-col items-center justify-center gap-3 shrink-0 select-none">
          {/* Lettres verticales */}
          {"HACKATONIA".split("").map((lettre, i) => (
            <span
              key={i}
              className="text-3xl font-black tracking-widest leading-none
                         text-sky-400 dark:text-sky-300
                         drop-shadow-[0_0_12px_rgba(56,189,248,0.6)]"
              style={{ animationDelay: `${i * 80}ms` }}
            >
              {lettre}
            </span>
          ))}
          <div className="mt-3 w-px h-16 bg-gradient-to-b from-sky-400 to-transparent dark:from-sky-300 opacity-60" />
          <p className="text-xs font-semibold text-sky-500 dark:text-sky-400 uppercase tracking-[0.3em] rotate-90 mt-2">
            2026
          </p>
        </div>

        {/* HACKATONIA sur mobile — une seule ligne sous la carte */}
      </div>

      {/* ── Pied de page mobile : HACKATONIA en ligne ── */}
      <div className="lg:hidden flex justify-center pb-6">
        <span className="text-lg font-black tracking-[0.4em] text-sky-400 dark:text-sky-300
                         drop-shadow-[0_0_8px_rgba(56,189,248,0.5)]">
          HACKATONIA
        </span>
      </div>
    </div>
  );
}

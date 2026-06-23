"use client";

/**
 * Écran de démarrage animé HACKATONIA — affiché à CHAQUE ouverture du site.
 *
 * Durée totale : 4 secondes
 *   t = 0      → fond bleu marine + logo apparaît (fade-in 300 ms)
 *   t = 300    → "Hackathon" se grave en bleu ciel (laser printing, 700 ms)
 *   t = 1000   → "Hackathon" reste affiché en lueur stable
 *   t = 1500   → "Réalisé par l'équipe HACKATONIA" se grave SOUS le titre
 *   t = 2200   → les deux textes restent affichés ensemble
 *   t = 3500   → fondu de sortie (500 ms)
 *   t = 4000   → démontage et révélation de l'app
 *
 * Politique d'affichage :
 *   - À chaque montage du composant racine (nouvelle fenêtre, F5, nouveau
 *     navigateur), le splash se rejoue.
 *   - Les navigations internes Next.js ne le rejouent PAS (root layout reste monté).
 *
 * Le splash NE bloque PAS le chargement des données — il est en `position: fixed`
 * au-dessus de l'app, qui continue d'hydrater en arrière-plan.
 *
 * Styles défensifs en inline : le splash reste visuellement correct même si
 * Tailwind n'a pas encore fini de charger (cas du tout premier rendu en dev).
 */

import Image from "next/image";
import { useEffect, useState } from "react";

// Durées en ms — synchronisées avec les keyframes CSS (cf. globals.css)
const DUREE_FADE_IN_LOGO = 300;
const DUREE_LASER = 700;
const PAUSE_APRES_TITRE = 500; // avant l'apparition du sous-titre
const DUREE_VISIBLE_FINAL = 1300; // les 2 textes ensemble avant fondu
const DUREE_FADE_OUT = 500;

// 300 + 700 + 500 + 700 + 1300 = 3500 ms
const TOTAL_AVANT_FONDU =
  DUREE_FADE_IN_LOGO +
  DUREE_LASER +
  PAUSE_APRES_TITRE +
  DUREE_LASER +
  DUREE_VISIBLE_FINAL;
// Durée totale visible = TOTAL_AVANT_FONDU + DUREE_FADE_OUT = 4000 ms

type Phase =
  | "init"
  | "titre"        // "Hackathon" apparaît en laser
  | "complet"      // sous-titre apparaît en laser, titre toujours visible
  | "fade-out"
  | "termine";

const COULEUR_BLEU_MARINE = "#0B2545";
const COULEUR_BLEU_CIEL = "#4CC9F0";

export function SplashScreen() {
  // `null` côté serveur (pas de mismatch d'hydration).
  // Côté client, on enchaîne directement init → titre → complet → fade-out → termine.
  const [phase, setPhase] = useState<Phase | null>(null);

  // Un seul effet qui s'exécute au MONTAGE et programme TOUS les timers en une fois.
  // CRITIQUE : la liste de dépendances est `[]` — sans ça, chaque changement de
  // phase rejouerait la cleanup et annulerait les timeouts suivants.
  useEffect(() => {
    setPhase("init");

    const t1 = setTimeout(() => setPhase("titre"), DUREE_FADE_IN_LOGO);
    const t2 = setTimeout(
      () => setPhase("complet"),
      DUREE_FADE_IN_LOGO + DUREE_LASER + PAUSE_APRES_TITRE,
    );
    const t3 = setTimeout(() => setPhase("fade-out"), TOTAL_AVANT_FONDU);
    const t4 = setTimeout(
      () => setPhase("termine"),
      TOTAL_AVANT_FONDU + DUREE_FADE_OUT,
    );

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      clearTimeout(t4);
    };
  }, []);

  if (phase === null || phase === "termine") return null;

  // Styles inline défensifs : garantissent un affichage correct
  // même si Tailwind n'a pas encore appliqué ses classes.
  const styleConteneur: React.CSSProperties = {
    position: "fixed",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 9999,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: "1.25rem",
    padding: "1rem",
    backgroundColor: COULEUR_BLEU_MARINE,
    transition: `opacity ${DUREE_FADE_OUT}ms ease-out`,
    opacity: phase === "fade-out" ? 0 : 1,
  };

  // À partir de "titre", on rend le titre.
  // À partir de "complet", on rend AUSSI le sous-titre.
  const afficherTitre = phase === "titre" || phase === "complet" || phase === "fade-out";
  const afficherSousTitre = phase === "complet" || phase === "fade-out";

  return (
    <div
      role="dialog"
      aria-label="Écran de démarrage"
      aria-live="polite"
      style={styleConteneur}
    >
      {/* Logo centré, fade-in doux */}
      <div
        className="splash-logo-wrapper"
        style={{
          width: "min(40vw, 12rem)",
          height: "min(40vw, 12rem)",
          position: "relative",
        }}
      >
        <Image
          src="/logo-hackathon.jpg"
          alt="Logo HACKATONIA"
          fill
          priority
          sizes="(max-width: 768px) 40vw, 12rem"
          style={{
            objectFit: "contain",
            borderRadius: "1rem",
            boxShadow: "0 8px 24px rgba(0,0,0,0.35)",
          }}
        />
      </div>

      {/* Zone des deux textes empilés (titre + sous-titre) */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "0.75rem",
          textAlign: "center",
        }}
      >
        {/* Titre — taille grande */}
        <div
          style={{
            minHeight: "3rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {afficherTitre && (
            <TexteLaser cle="titre" taille="grand">
              Hackathon
            </TexteLaser>
          )}
        </div>

        {/* Sous-titre — taille plus petite, sous le titre */}
        <div
          style={{
            minHeight: "1.75rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {afficherSousTitre && (
            <TexteLaser cle="soustitre" taille="petit">
              Réalisé par l&apos;équipe HACKATONIA
            </TexteLaser>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Texte rendu avec l'effet "laser printing" en bleu ciel.
 * L'animation principale est portée par la classe `splash-laser-text`
 * (cf. app/globals.css). Le `key` force le redémarrage de l'animation
 * à chaque changement de texte.
 */
function TexteLaser({
  children,
  cle,
  taille,
}: {
  children: React.ReactNode;
  cle: string;
  taille: "grand" | "petit";
}) {
  const styles: React.CSSProperties = {
    display: "inline-block",
    whiteSpace: "nowrap",
    color: COULEUR_BLEU_CIEL,
    fontWeight: taille === "grand" ? 700 : 500,
    letterSpacing: taille === "grand" ? "0.04em" : "0.02em",
    fontSize:
      taille === "grand"
        ? "clamp(1.6rem, 5vw, 2.75rem)"
        : "clamp(0.9rem, 2.6vw, 1.25rem)",
    // Pas de textShadow : on veut juste les écrits clairs en bleu ciel,
    // sans halo qui se superpose sur les caractères.
  };

  return (
    <span key={cle} className="splash-laser-text" style={styles}>
      {children}
    </span>
  );
}

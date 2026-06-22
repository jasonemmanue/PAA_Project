import type { Config } from "tailwindcss";

/**
 * Design system PAA-Traverse — palette dérivée de l'identité visuelle du
 * Port Autonome d'Abidjan (bandeau bleu marine foncé, en-têtes bleu clair).
 *
 * Conventions :
 *  - `paa.navy.*`  : bandeaux principaux, fond sombre des panneaux de tête.
 *  - `paa.blue.*`  : surfaces secondaires, en-têtes de tableaux, accents.
 *  - `paa.sky`     : RÉSERVÉ exclusivement à la ligne de référence 50 km/h
 *                    (norme du cahier des charges). Ne pas l'utiliser ailleurs.
 *  - `statut.*`    : couleurs des niveaux de congestion (FHWA, cf. CLAUDE.md § 5).
 *
 * Trois points de rupture explicites :
 *   sm = 375px (mobile),  md = 768px (tablette),  lg = 1024px (desktop).
 */
const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    screens: {
      sm: "375px",
      md: "768px",
      lg: "1024px",
      xl: "1280px",
      "2xl": "1536px",
    },
    container: {
      center: true,
      padding: {
        DEFAULT: "1rem",
        md: "1.5rem",
        lg: "2rem",
      },
    },
    extend: {
      colors: {
        paa: {
          navy: {
            900: "#0B2545", // bandeau principal — très sombre
            800: "#13315C",
            700: "#1F4E79", // accents foncés (boutons, en-têtes)
            600: "#2E5C8A",
          },
          blue: {
            500: "#2E86AB", // primary action
            400: "#5DA5C9",
            300: "#A6BBD9",
            200: "#C5D5EA",
            100: "#D9E2F3", // en-têtes de tableaux clairs
            50: "#EFF4FA",  // surface très claire
          },
          // RÉSERVÉ : ligne de référence 50 km/h (cf. cahier des charges)
          sky: "#4CC9F0",
        },
        statut: {
          // Palette DEESP — rapport oct. 2025 § METHODOLOGIE (cf. CLAUDE.md § 4.5.2).
          // Plus de classe "dense" : la qualification ne distingue que
          // fluide / congestionné selon la couleur Google Maps. `dense` est
          // conservé comme alias couleur pour les usages non-congestion
          // (warnings, jauges de calibration).
          fluide: "#2ECC71",        // vert — vert + orange court
          dense: "#F39C12",         // orange — usage warnings uniquement
          congestionne: "#E74C3C",  // rouge — ROUGE ou ORANGE long
          indetermine: "#95A5A6",   // gris — pas de couleur Google Maps
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "Consolas", "monospace"],
      },
      fontSize: {
        // Tailles fluides utilisant clamp() — s'adaptent automatiquement à la
        // largeur de l'écran sans valeur fixe en pixels.
        "fluid-xs": "clamp(0.7rem, 1.4vw, 0.75rem)",
        "fluid-sm": "clamp(0.8rem, 1.6vw, 0.875rem)",
        "fluid-base": "clamp(0.9rem, 1.8vw, 1rem)",
        "fluid-lg": "clamp(1rem, 2.2vw, 1.125rem)",
        "fluid-xl": "clamp(1.125rem, 2.6vw, 1.375rem)",
        "fluid-2xl": "clamp(1.375rem, 3.4vw, 1.75rem)",
        "fluid-3xl": "clamp(1.625rem, 4.4vw, 2.25rem)",
      },
      spacing: {
        // Espacements fluides pour gouttières et marges
        "fluid-2": "clamp(0.375rem, 1vw, 0.5rem)",
        "fluid-4": "clamp(0.75rem, 2vw, 1rem)",
        "fluid-6": "clamp(1rem, 3vw, 1.5rem)",
        "fluid-8": "clamp(1.5rem, 4vw, 2rem)",
      },
      boxShadow: {
        "paa-sm": "0 1px 2px rgba(11, 37, 69, 0.06)",
        "paa-md": "0 4px 12px rgba(11, 37, 69, 0.08)",
        "paa-lg": "0 8px 24px rgba(11, 37, 69, 0.10)",
      },
      animation: {
        "fade-in": "fade-in 200ms ease-out",
        "slide-in-left": "slide-in-left 240ms cubic-bezier(0.16, 1, 0.3, 1)",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "slide-in-left": {
          from: { transform: "translateX(-100%)" },
          to: { transform: "translateX(0)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;

/**
 * Icônes SVG inline pour éviter une dépendance externe.
 * Toutes les icônes acceptent les props standard SVG.
 */

import type { SVGProps } from "react";

const PROPS_PAR_DEFAUT: SVGProps<SVGSVGElement> = {
  width: 20,
  height: 20,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
};

export function IconCarte(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...PROPS_PAR_DEFAUT} {...props}>
      <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
      <line x1="8" y1="2" x2="8" y2="18" />
      <line x1="16" y1="6" x2="16" y2="22" />
    </svg>
  );
}

export function IconIndicateurs(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...PROPS_PAR_DEFAUT} {...props}>
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  );
}

export function IconFiabilite(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...PROPS_PAR_DEFAUT} {...props}>
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  );
}

export function IconPrediction(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...PROPS_PAR_DEFAUT} {...props}>
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

export function IconAdmin(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...PROPS_PAR_DEFAUT} {...props}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

export function IconBurger(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...PROPS_PAR_DEFAUT} {...props}>
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="12" x2="21" y2="12" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  );
}

export function IconClose(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...PROPS_PAR_DEFAUT} {...props}>
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

export function IconChevronLeft(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...PROPS_PAR_DEFAUT} {...props}>
      <polyline points="15 18 9 12 15 6" />
    </svg>
  );
}

export function IconChevronRight(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...PROPS_PAR_DEFAUT} {...props}>
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

export function IconIncidents(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...PROPS_PAR_DEFAUT} {...props}>
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

export function IconHeureOptimale(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...PROPS_PAR_DEFAUT} {...props}>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 6v6l4 2" />
      <path d="M16.24 7.76a6 6 0 0 1 0 8.49" strokeDasharray="2 2" />
    </svg>
  );
}

export function IconChatbot(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...PROPS_PAR_DEFAUT} {...props}>
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      <line x1="9" y1="10" x2="9" y2="10" strokeWidth="3" strokeLinecap="round" />
      <line x1="12" y1="10" x2="12" y2="10" strokeWidth="3" strokeLinecap="round" />
      <line x1="15" y1="10" x2="15" y2="10" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function IconGlobe(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...PROPS_PAR_DEFAUT} {...props}>
      <circle cx="12" cy="12" r="10" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  );
}

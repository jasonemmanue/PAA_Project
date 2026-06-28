"use client";

/**
 * Source de vérité des entrées de navigation principales.
 * Utilisée par la sidebar desktop ET par le drawer mobile.
 */

import {
  IconCarte,
  IconHeureOptimale,
  IconIndicateurs,
  IconFiabilite,
  IconIncidents,
  IconPrediction,
  IconAdmin,
} from "@/components/ui/Icons";
import type { ComponentType, SVGProps } from "react";

export type EntreeNav = {
  href: string;
  labelKey: string;
  Icon: ComponentType<SVGProps<SVGSVGElement>>;
};

export const ENTREES_NAV: EntreeNav[] = [
  { href: "/", labelKey: "nav.carte", Icon: IconCarte },
  { href: "/rapport", labelKey: "nav.rapport", Icon: IconIndicateurs },
  { href: "/indicateurs", labelKey: "nav.indicateurs", Icon: IconIndicateurs },
  { href: "/prediction", labelKey: "nav.prediction", Icon: IconPrediction },
  { href: "/heure-optimale", labelKey: "nav.heureOptimale", Icon: IconHeureOptimale },
  { href: "/incidents", labelKey: "nav.incidents", Icon: IconIncidents },
  { href: "/fiabilite", labelKey: "nav.fiabilite", Icon: IconFiabilite },
  { href: "/administration", labelKey: "nav.administration", Icon: IconAdmin },
];

"use client";

/**
 * Source de vérité des entrées de navigation principales.
 * Utilisée par la sidebar desktop ET par le drawer mobile.
 */

import {
  IconCarte,
  IconIndicateurs,
  IconFiabilite,
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
  { href: "/indicateurs", labelKey: "nav.indicateurs", Icon: IconIndicateurs },
  { href: "/rapport", labelKey: "nav.rapport", Icon: IconIndicateurs },
  { href: "/fiabilite", labelKey: "nav.fiabilite", Icon: IconFiabilite },
  { href: "/prediction", labelKey: "nav.prediction", Icon: IconPrediction },
  { href: "/administration", labelKey: "nav.administration", Icon: IconAdmin },
];

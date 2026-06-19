"use client";

/**
 * Page d'accueil — vue Carte. C'est ici que sera intégrée la carte Leaflet
 * (étape suivante de P4). Cette coquille présente déjà la structure :
 *   - panneau de légende des couleurs (responsive : top sur mobile, côté sur desktop)
 *   - zone principale réservée à la carte (placeholder)
 *   - bandeau d'état temps réel (date/heure de dernière mesure)
 */

import { Card, Placeholder } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatutBadge } from "@/components/ui/StatutBadge";
import { useI18n } from "@/lib/i18n";

export default function PageAccueil() {
  const { t } = useI18n();

  return (
    <div className="flex flex-col gap-fluid-4">
      <PageHeader titre={t("carte.title")} sousTitre={t("carte.subtitle")} />

      {/* Grille principale : 1 col mobile, 2 col tablette+, ratio 2:1 sur desktop */}
      <div className="grid gap-fluid-4 md:grid-cols-3 lg:grid-cols-4">
        {/* Zone carte (prend la place restante) */}
        <Card className="md:col-span-2 lg:col-span-3">
          <Placeholder message={t("carte.placeholder")} />
        </Card>

        {/* Panneau de légende */}
        <Card titre={t("carte.legendTitle")}>
          <ul className="space-y-2">
            <li className="flex items-center justify-between gap-2">
              <span className="text-fluid-sm">{t("carte.legendFluide")}</span>
              <StatutBadge classe="fluide" />
            </li>
            <li className="flex items-center justify-between gap-2">
              <span className="text-fluid-sm">{t("carte.legendDense")}</span>
              <StatutBadge classe="dense" />
            </li>
            <li className="flex items-center justify-between gap-2">
              <span className="text-fluid-sm">
                {t("carte.legendCongestionne")}
              </span>
              <StatutBadge classe="congestionne" />
            </li>
            <li className="flex items-center justify-between gap-2">
              <span className="text-fluid-sm">
                {t("carte.legendIndetermine")}
              </span>
              <StatutBadge classe="indetermine" />
            </li>
            <li className="mt-3 flex items-center gap-2 border-t app-border pt-3">
              <span
                className="inline-block h-1 w-8 rounded-full"
                style={{ background: "#4CC9F0" }}
                aria-hidden
              />
              <span className="text-fluid-xs app-text-muted">
                {t("carte.referenceLine")}
              </span>
            </li>
          </ul>
        </Card>
      </div>
    </div>
  );
}

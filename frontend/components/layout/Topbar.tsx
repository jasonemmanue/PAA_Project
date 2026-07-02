"use client";

/**
 * Bandeau supérieur de l'application — affichage du nom, du sélecteur de
 * langue, du basculeur de thème, et du bouton burger (mobile / tablette).
 * Utilise la couleur identitaire PAA (bleu marine foncé).
 */

import { useI18n } from "@/lib/i18n";
import { IconBurger } from "@/components/ui/Icons";
import { LangSwitcher } from "@/components/i18n/LangSwitcher";
import { SelecteurPlageHoraire } from "@/components/layout/SelecteurPlageHoraire";
import { ThemeToggle } from "@/components/theme/ThemeToggle";

export function Topbar({ ouvrirMenu }: { ouvrirMenu: () => void }) {
  const { t } = useI18n();

  return (
    <header className="paa-banner sticky top-0 z-[1100]">
      <div className="flex items-center justify-between gap-3 px-fluid-4 py-3">
        {/* Bouton burger — visible sur mobile et tablette uniquement */}
        <button
          type="button"
          onClick={ouvrirMenu}
          aria-label={t("common.menu")}
          className="inline-flex h-10 w-10 items-center justify-center rounded-md
                     text-white hover:bg-white/10 lg:hidden"
        >
          <IconBurger />
        </button>

        {/* Titre app + sous-titre (caché sur mobile pour gain de place) */}
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="truncate text-fluid-lg font-semibold tracking-tight">
            {t("appName")}
          </span>
          <span className="hidden truncate text-fluid-xs text-paa-blue-200 md:block">
            {t("appTagline")}
          </span>
        </div>

        {/* Plage horaire + langue + thème */}
        <div className="flex items-center gap-2">
          <SelecteurPlageHoraire />
          <LangSwitcher />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

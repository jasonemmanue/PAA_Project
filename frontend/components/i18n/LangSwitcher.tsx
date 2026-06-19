"use client";

/**
 * Bouton de bascule FR / EN — switch immédiat sans rechargement,
 * persisté dans localStorage par le provider i18n.
 */

import clsx from "clsx";

import { useI18n } from "@/lib/i18n";
import { IconGlobe } from "@/components/ui/Icons";

export function LangSwitcher() {
  const { locale, setLocale, t } = useI18n();

  return (
    <div
      role="group"
      aria-label={t("common.language")}
      className="inline-flex items-center gap-1 rounded-md border app-border
                 bg-white p-1 dark:bg-paa-navy-800"
    >
      <IconGlobe className="ml-1 hidden md:block text-paa-navy-700 dark:text-paa-blue-100" />
      {(["fr", "en"] as const).map((code) => {
        const actif = locale === code;
        return (
          <button
            key={code}
            type="button"
            onClick={() => setLocale(code)}
            aria-pressed={actif}
            className={clsx(
              "px-2.5 py-1 text-fluid-sm font-medium uppercase tracking-wide rounded transition-colors min-h-[36px]",
              actif
                ? "bg-paa-navy-700 text-white"
                : "text-paa-navy-700 hover:bg-paa-blue-50 dark:text-paa-blue-100 dark:hover:bg-paa-navy-700",
            )}
          >
            {code}
          </button>
        );
      })}
    </div>
  );
}

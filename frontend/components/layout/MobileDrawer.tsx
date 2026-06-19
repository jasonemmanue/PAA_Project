"use client";

/**
 * Drawer mobile / tablette — affiché lorsque la sidebar n'est pas accessible
 * (< 1024 px). S'ouvre depuis le bouton burger du topbar, se ferme en cliquant
 * en dehors, en pressant Échap, ou via un lien.
 */

import clsx from "clsx";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { ENTREES_NAV } from "./NavItems";
import { useI18n } from "@/lib/i18n";
import { IconClose } from "@/components/ui/Icons";

export function MobileDrawer({
  ouvert,
  fermer,
}: {
  ouvert: boolean;
  fermer: () => void;
}) {
  const pathname = usePathname();
  const { t } = useI18n();

  // Échap pour fermer
  useEffect(() => {
    if (!ouvert) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") fermer();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [ouvert, fermer]);

  // Bloque le scroll du body quand le drawer est ouvert
  useEffect(() => {
    if (!ouvert) return;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
    };
  }, [ouvert]);

  return (
    <>
      {/* Voile semi-transparent */}
      <div
        className={clsx(
          "fixed inset-0 z-40 bg-black/40 transition-opacity lg:hidden",
          ouvert ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        aria-hidden
        onClick={fermer}
      />

      {/* Panneau du drawer */}
      <aside
        aria-label="Navigation"
        aria-hidden={!ouvert}
        className={clsx(
          "fixed inset-y-0 left-0 z-50 w-72 max-w-[85vw] app-surface border-r app-border",
          "shadow-paa-lg transition-transform duration-200 lg:hidden",
          ouvert ? "translate-x-0" : "-translate-x-full",
        )}
      >
        {/* En-tête du drawer */}
        <div className="flex items-center justify-between border-b app-border px-4 py-3">
          <div className="flex items-center gap-2">
            <span
              className="flex h-9 w-9 items-center justify-center rounded-md
                         bg-paa-navy-900 text-white font-bold text-sm"
            >
              PAA
            </span>
            <span className="font-semibold">{t("appName")}</span>
          </div>
          <button
            type="button"
            onClick={fermer}
            aria-label={t("common.close")}
            className="inline-flex h-10 w-10 items-center justify-center rounded-md
                       text-paa-navy-900 hover:bg-paa-blue-50
                       dark:text-paa-blue-100 dark:hover:bg-paa-navy-700"
          >
            <IconClose />
          </button>
        </div>

        {/* Entrées de navigation */}
        <nav className="px-2 py-2">
          <ul className="space-y-1">
            {ENTREES_NAV.map(({ href, labelKey, Icon }) => {
              const actif =
                href === "/"
                  ? pathname === "/"
                  : pathname?.startsWith(href);
              return (
                <li key={href}>
                  <Link
                    href={href}
                    onClick={fermer}
                    className={clsx(
                      "flex items-center gap-3 rounded-md px-3 py-3 text-fluid-base font-medium transition-colors",
                      actif
                        ? "bg-paa-blue-100 text-paa-navy-900 dark:bg-paa-navy-700 dark:text-paa-blue-100"
                        : "text-paa-navy-900 hover:bg-paa-blue-50 dark:text-paa-blue-200 dark:hover:bg-paa-navy-700",
                    )}
                  >
                    <Icon className="shrink-0" />
                    <span>{t(labelKey)}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </aside>
    </>
  );
}

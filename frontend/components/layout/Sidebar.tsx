"use client";

/**
 * Sidebar desktop — visible à partir du breakpoint `lg` (≥ 1024 px).
 * Peut être réduite à une largeur d'icônes seulement via la prop `replie`.
 * Sur tablette et mobile, la sidebar disparaît : la navigation passe par
 * le drawer (<MobileDrawer />) déclenché depuis le burger du topbar.
 */

import clsx from "clsx";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { ENTREES_NAV } from "./NavItems";
import { useI18n } from "@/lib/i18n";
import { IconChevronLeft, IconChevronRight } from "@/components/ui/Icons";

export function Sidebar({
  replie,
  basculerReplie,
  nbIncidentsActifs = 0,
}: {
  replie: boolean;
  basculerReplie: () => void;
  nbIncidentsActifs?: number;
}) {
  const pathname = usePathname();
  const { t } = useI18n();

  return (
    <aside
      aria-label="Navigation principale"
      className={clsx(
        "hidden lg:flex shrink-0 flex-col gap-2 border-r app-border app-surface transition-[width] duration-200",
        replie ? "w-16" : "w-64",
      )}
    >
      {/* Logo + nom de l'app */}
      <div
        className={clsx(
          "flex items-center gap-2 border-b app-border px-3 py-4",
          replie ? "justify-center" : "justify-start",
        )}
      >
        <span
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md
                     bg-paa-navy-900 text-white font-bold text-sm"
          aria-hidden
        >
          PAA
        </span>
        {!replie && (
          <span className="font-semibold text-fluid-base truncate">
            {t("appName")}
          </span>
        )}
      </div>

      {/* Entrées de navigation */}
      <nav className="flex-1 px-2 py-2">
        <ul className="space-y-1">
          {ENTREES_NAV.map(({ href, labelKey, Icon }) => {
            const actif =
              href === "/"
                ? pathname === "/"
                : pathname?.startsWith(href);
            const badgeIncidents = href === "/incidents" && nbIncidentsActifs > 0;
            return (
              <li key={href}>
                <Link
                  href={href}
                  title={replie ? t(labelKey) : undefined}
                  className={clsx(
                    "flex items-center gap-3 rounded-md px-2.5 py-2.5 text-fluid-sm font-medium transition-colors",
                    actif
                      ? "bg-paa-blue-100 text-paa-navy-900 dark:bg-paa-navy-700 dark:text-paa-blue-100"
                      : "text-paa-navy-900 hover:bg-paa-blue-50 dark:text-paa-blue-200 dark:hover:bg-paa-navy-700",
                    replie && "justify-center",
                  )}
                >
                  <span className="relative shrink-0">
                    <Icon />
                    {badgeIncidents && (
                      <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center
                                       rounded-full bg-red-600 text-[9px] font-bold text-white">
                        {nbIncidentsActifs > 9 ? "9+" : nbIncidentsActifs}
                      </span>
                    )}
                  </span>
                  {!replie && <span className="truncate">{t(labelKey)}</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Bouton de bascule replier/déplier */}
      <div className="border-t app-border p-2">
        <button
          type="button"
          onClick={basculerReplie}
          className="flex w-full items-center justify-center rounded-md py-2 text-paa-navy-700
                     hover:bg-paa-blue-50 dark:text-paa-blue-100 dark:hover:bg-paa-navy-700"
          aria-label={replie ? "Déplier la barre latérale" : "Replier la barre latérale"}
        >
          {replie ? <IconChevronRight /> : <IconChevronLeft />}
        </button>
      </div>
    </aside>
  );
}

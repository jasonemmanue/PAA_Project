"use client";

/**
 * Coquille générique de l'application :
 *   - <Topbar/>     bandeau supérieur (logo, langue, thème, burger)
 *   - <Sidebar/>    barre latérale verticale (desktop uniquement, repliable)
 *   - <MobileDrawer/> tiroir mobile / tablette
 *   - {children}    contenu de la page en cours
 *
 * Le `flex-col lg:flex-row` ci-dessous garantit que sur les petites tailles,
 * la sidebar (cachée par CSS) ne prend pas d'espace : le topbar + main
 * occupent toute la largeur. Sur desktop, sidebar + main vivent côte à côte.
 */

import { useState, type ReactNode } from "react";

import { MobileDrawer } from "./MobileDrawer";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { useI18n } from "@/lib/i18n";

export function AppShell({ children }: { children: ReactNode }) {
  const [drawerOuvert, setDrawerOuvert] = useState(false);
  const [sidebarRepliee, setSidebarRepliee] = useState(false);
  const { t } = useI18n();

  return (
    <div className="flex min-h-dvh flex-col lg:flex-row">
      <Sidebar
        replie={sidebarRepliee}
        basculerReplie={() => setSidebarRepliee((v) => !v)}
      />

      <MobileDrawer
        ouvert={drawerOuvert}
        fermer={() => setDrawerOuvert(false)}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar ouvrirMenu={() => setDrawerOuvert(true)} />

        <main
          className="flex-1 px-fluid-4 py-fluid-6 lg:px-fluid-8 lg:py-fluid-8
                     bg-[rgb(var(--app-bg))]"
        >
          {children}
        </main>

        <footer className="border-t app-border app-surface px-fluid-4 py-3 text-center text-fluid-xs app-text-muted">
          {t("footer.tagline")}
        </footer>
      </div>
    </div>
  );
}

"use client";

/**
 * Provider d'internationalisation côté client.
 *
 * Choix : on n'utilise pas la i18n basée sur les routes de Next.js
 * (qui impose des préfixes `/fr/...`, `/en/...` et un rechargement à la
 * bascule). À la place, on stocke la locale dans un Context React et on
 * permute les dictionnaires en mémoire — la bascule FR/EN est donc
 * **immédiate, sans rechargement de page**.
 *
 * Persistance : la langue choisie est sauvegardée dans `localStorage`
 * sous la clé `paa-locale`, restaurée au prochain chargement.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import frMessages from "@/messages/fr.json";
import enMessages from "@/messages/en.json";

export type Locale = "fr" | "en";

type MessagesShape = typeof frMessages;

const DICTIONARIES: Record<Locale, MessagesShape> = {
  fr: frMessages,
  en: enMessages as unknown as MessagesShape,
};

const STORAGE_KEY = "paa-locale";

type I18nContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  /** Récupère un message via un chemin pointé : `t("nav.carte")`. */
  t: (path: string) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);

function lireMessage(dict: MessagesShape, path: string): string {
  const segments = path.split(".");
  let current: unknown = dict;
  for (const segment of segments) {
    if (typeof current !== "object" || current === null) return path;
    current = (current as Record<string, unknown>)[segment];
  }
  return typeof current === "string" ? current : path;
}

function determinerLocaleInitiale(localeProp: Locale): Locale {
  if (typeof window === "undefined") return localeProp;
  const stockee = window.localStorage.getItem(STORAGE_KEY);
  if (stockee === "fr" || stockee === "en") return stockee;
  return localeProp;
}

export function I18nProvider({
  children,
  defaultLocale = "fr",
}: {
  children: ReactNode;
  defaultLocale?: Locale;
}) {
  // Initialisé à la valeur SSR pour éviter une mismatch côté serveur,
  // puis remplacé par la valeur localStorage côté client (effet ci-dessous).
  const [locale, setLocaleState] = useState<Locale>(defaultLocale);

  useEffect(() => {
    const choisie = determinerLocaleInitiale(defaultLocale);
    if (choisie !== locale) setLocaleState(choisie);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Met à jour l'attribut <html lang="..."> pour l'accessibilité et le SEO
  useEffect(() => {
    if (typeof document !== "undefined") {
      document.documentElement.lang = locale;
    }
  }, [locale]);

  const setLocale = useCallback((nouvelle: Locale) => {
    setLocaleState(nouvelle);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, nouvelle);
    }
  }, []);

  const dict = DICTIONARIES[locale];

  const t = useCallback((path: string) => lireMessage(dict, path), [dict]);

  const value = useMemo(
    () => ({ locale, setLocale, t }),
    [locale, setLocale, t],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error(
      "useI18n doit être utilisé à l'intérieur de <I18nProvider>.",
    );
  }
  return ctx;
}

/** Helper court : hook qui retourne uniquement la fonction `t`. */
export function useT() {
  return useI18n().t;
}

"use client";

import { useState } from "react";

import { PasswordGate } from "@/components/auth/PasswordGate";
import { AppShell } from "@/components/layout/AppShell";
import { SplashScreen } from "@/components/SplashScreen";
import { AuthProvider, type NiveauAcces } from "@/contexts/AuthContext";
import { PlageHoraireProvider } from "@/contexts/PlageHoraireContext";

interface Props {
  children: React.ReactNode;
}

/**
 * Wrapper client qui séquence : portail mot de passe → splash screen → app.
 * L'état d'authentification est en mémoire pure (réinitialisé à chaque refresh/nouvel onglet).
 */
export function ClientLayout({ children }: Props) {
  const [niveau, setNiveau] = useState<NiveauAcces | null>(null);

  if (niveau === null) {
    return <PasswordGate onAuthentifie={setNiveau} />;
  }

  return (
    <AuthProvider niveau={niveau}>
      <PlageHoraireProvider>
        <AppShell>{children}</AppShell>
        <SplashScreen />
      </PlageHoraireProvider>
    </AuthProvider>
  );
}

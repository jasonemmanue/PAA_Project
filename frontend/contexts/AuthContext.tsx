"use client";

import { createContext, useContext, type ReactNode } from "react";

export type NiveauAcces = "lecture" | "ecriture";

interface AuthContextType {
  niveau: NiveauAcces;
  peutEcrire: boolean;
}

const AuthContext = createContext<AuthContextType>({
  niveau: "lecture",
  peutEcrire: false,
});

export function AuthProvider({
  niveau,
  children,
}: {
  niveau: NiveauAcces;
  children: ReactNode;
}) {
  return (
    <AuthContext.Provider value={{ niveau, peutEcrire: niveau === "ecriture" }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

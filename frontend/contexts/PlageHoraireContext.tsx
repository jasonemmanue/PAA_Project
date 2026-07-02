"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

interface PlageHoraireContextType {
  heureDebut: number;
  heureFin: number;
  setPlage: (debut: number, fin: number) => void;
  plageLabel: string;
  est24h: boolean;
}

const PlageHoraireContext = createContext<PlageHoraireContextType>({
  heureDebut: 0,
  heureFin: 24,
  setPlage: () => {},
  plageLabel: "24h/24",
  est24h: true,
});

const CLE_DEBUT = "paa_plage_h_debut";
const CLE_FIN = "paa_plage_h_fin";

export function PlageHoraireProvider({ children }: { children: ReactNode }) {
  const [heureDebut, setHeureDebut] = useState(0);
  const [heureFin, setHeureFin] = useState(24);

  useEffect(() => {
    const d = localStorage.getItem(CLE_DEBUT);
    const f = localStorage.getItem(CLE_FIN);
    if (d !== null && f !== null) {
      const dN = Number(d);
      const fN = Number(f);
      if (!isNaN(dN) && !isNaN(fN) && dN >= 0 && dN <= 23 && fN >= 1 && fN <= 24 && dN < fN) {
        setHeureDebut(dN);
        setHeureFin(fN);
      }
    }
  }, []);

  const setPlage = useCallback((debut: number, fin: number) => {
    setHeureDebut(debut);
    setHeureFin(fin);
    localStorage.setItem(CLE_DEBUT, String(debut));
    localStorage.setItem(CLE_FIN, String(fin));
  }, []);

  const est24h = heureDebut === 0 && heureFin === 24;
  const plageLabel = est24h
    ? "24h/24"
    : `${String(heureDebut).padStart(2, "0")}h – ${String(heureFin).padStart(2, "0")}h`;

  return (
    <PlageHoraireContext.Provider
      value={{ heureDebut, heureFin, setPlage, plageLabel, est24h }}
    >
      {children}
    </PlageHoraireContext.Provider>
  );
}

export function usePlageHoraire() {
  return useContext(PlageHoraireContext);
}

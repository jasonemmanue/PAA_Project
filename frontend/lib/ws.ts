"use client";

/**
 * Hook React de connexion au WebSocket `/ws/etat` du backend.
 *
 * - Reconnexion exponentielle en cas de coupure (1 s → 2 s → 4 s → 8 s, plafond 30 s).
 * - Décodage JSON et appel du callback `onMessage` à chaque trame reçue.
 * - Cleanup propre : ferme la socket à l'unmount du composant.
 */

import { useEffect, useRef, useState } from "react";

import type { CarteEtat } from "./types";

export type WsMessage =
  | { type: "snapshot"; donnees: CarteEtat }
  | { type: "maj"; donnees: CarteEtat };

function deriveWebsocketUrl(): string {
  const base =
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8081";
  return base.replace(/^http/, "ws").replace(/\/+$/, "") + "/ws/etat";
}

export type EtatConnexionWs = "connecting" | "open" | "closed";

export function useWsCarteEtat(
  onMessage: (msg: WsMessage) => void,
  options?: { actif?: boolean },
): EtatConnexionWs {
  const [etat, setEtat] = useState<EtatConnexionWs>("connecting");
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    if (options?.actif === false) return;

    let socket: WebSocket | null = null;
    let demonte = false;
    let tentative = 0;
    let timerReconnexion: ReturnType<typeof setTimeout> | null = null;

    const ouvrir = () => {
      if (demonte) return;
      try {
        setEtat("connecting");
        socket = new WebSocket(deriveWebsocketUrl());
      } catch {
        replanifier();
        return;
      }

      socket.onopen = () => {
        if (demonte) return;
        tentative = 0;
        setEtat("open");
      };

      socket.onmessage = (event) => {
        if (demonte) return;
        try {
          const msg = JSON.parse(event.data) as WsMessage;
          onMessageRef.current(msg);
        } catch {
          // Trame illisible — on l'ignore
        }
      };

      socket.onclose = () => {
        if (demonte) return;
        setEtat("closed");
        replanifier();
      };

      socket.onerror = () => {
        // socket.close() suivra → géré par onclose
      };
    };

    const replanifier = () => {
      if (demonte) return;
      tentative += 1;
      const delai = Math.min(30_000, 1_000 * 2 ** Math.min(tentative, 5));
      timerReconnexion = setTimeout(ouvrir, delai);
    };

    ouvrir();

    return () => {
      demonte = true;
      if (timerReconnexion) clearTimeout(timerReconnexion);
      socket?.close();
    };
  }, [options?.actif]);

  return etat;
}

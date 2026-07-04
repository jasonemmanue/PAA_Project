"use client";

import { useEffect, useRef, useState } from "react";
import { IconChatbot, IconClose } from "@/components/ui/Icons";
import { useI18n } from "@/lib/i18n";

const QUESTIONS_SUGGEREES = [
  "Comment lire la carte principale ?",
  "Quelle est la meilleure heure pour livrer au port ?",
  "Comment exporter le rapport DEESP ?",
  "Comment importer une trace GPS terrain ?",
];

interface Message {
  role: "user" | "assistant";
  texte: string;
}

/**
 * Appelle l'endpoint SSE /chatbot/stream et pousse chaque delta reçu via
 * `onDelta` — permet un affichage lettre-par-lettre côté UI.
 */
async function streamerClaude(
  apiBaseUrl: string,
  historique: Message[],
  question: string,
  onDelta: (chunk: string) => void,
): Promise<void> {
  const res = await fetch(`${apiBaseUrl}/chatbot/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      historique: historique.map((m) => ({ role: m.role, texte: m.texte })),
      question,
    }),
  });

  if (!res.ok || !res.body) {
    const corps = await res.text().catch(() => "");
    let detail = corps.slice(0, 300);
    try { detail = JSON.parse(corps)?.detail ?? detail; } catch { /* non-JSON */ }
    throw new Error(detail || `HTTP ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let tampon = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    tampon += decoder.decode(value, { stream: true });

    // Consomme le tampon événement par événement (séparés par \n\n)
    let idx: number;
    while ((idx = tampon.indexOf("\n\n")) !== -1) {
      const evt = tampon.slice(0, idx);
      tampon = tampon.slice(idx + 2);
      for (const ligne of evt.split("\n")) {
        if (!ligne.startsWith("data:")) continue;
        const charge = ligne.slice(5).trim();
        if (!charge || charge === "[DONE]") continue;
        try {
          const obj = JSON.parse(charge);
          if (obj.erreur) throw new Error(obj.erreur);
          if (typeof obj.delta === "string" && obj.delta.length > 0) {
            onDelta(obj.delta);
          }
        } catch (e) {
          if (e instanceof Error && e.message !== "Unexpected end of JSON input") {
            throw e;
          }
        }
      }
    }
  }
}

// Vitesse de révélation de l'effet "laser printing" (ms entre chaque caractère).
// Trop lent = agaçant ; trop rapide = perte de l'effet. ~14 ms est un bon
// compromis (~70 caractères/seconde, cadence de dactylo rapide).
const LASER_TICK_MS = 14;
// Nombre de caractères révélés à chaque tick — permet de rattraper si le
// backend nous envoie une grande rafale d'un coup sans faire attendre l'user.
const LASER_CHARS_PAR_TICK = 1;
// Au-delà de ce retard buffer, on accélère pour rattraper.
const LASER_RATTRAPAGE_SEUIL = 40;

export function ChatbotButton() {
  const { t } = useI18n();
  const [ouvert, setOuvert] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [saisie, setSaisie] = useState("");
  const [envoi, setEnvoi] = useState(false);
  const [streamActif, setStreamActif] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8081";
  const basRef = useRef<HTMLDivElement>(null);

  // Buffer complet reçu du serveur (indépendant du texte affiché).
  const bufferRef = useRef<string>("");
  // Portion déjà révélée à l'écran.
  const revealeRef = useRef<string>("");
  // True quand le serveur a fini d'envoyer (le loop peut s'arrêter dès
  // que revealeRef.current a rattrapé bufferRef.current).
  const streamTermineRef = useRef<boolean>(false);
  // ID du setInterval de révélation — pour nettoyage.
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (basRef.current) {
      basRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  // Nettoyage global à l'unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  function demarrerRevelation() {
    if (intervalRef.current) return;
    intervalRef.current = setInterval(() => {
      const buf = bufferRef.current;
      const revele = revealeRef.current;
      if (revele.length >= buf.length) {
        // Rien de nouveau à révéler pour l'instant
        if (streamTermineRef.current) {
          // Fin du stream et tout est affiché → on stoppe
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
          setStreamActif(false);
        }
        return;
      }
      // Détermine combien de caractères ajouter ce tick — on accélère
      // si le buffer prend beaucoup d'avance (rafales SSE).
      const retard = buf.length - revele.length;
      const pas = retard > LASER_RATTRAPAGE_SEUIL
        ? Math.max(LASER_CHARS_PAR_TICK, Math.ceil(retard / 20))
        : LASER_CHARS_PAR_TICK;
      const suivant = buf.slice(0, revele.length + pas);
      revealeRef.current = suivant;
      setMessages((prev) => {
        const copie = prev.slice();
        const dernier = copie[copie.length - 1];
        if (dernier && dernier.role === "assistant") {
          copie[copie.length - 1] = { ...dernier, texte: suivant };
        }
        return copie;
      });
    }, LASER_TICK_MS);
  }

  async function envoyer() {
    const question = saisie.trim();
    if (!question || envoi) return;

    const historiqueAvant = messages;

    // Reset des buffers de streaming
    bufferRef.current = "";
    revealeRef.current = "";
    streamTermineRef.current = false;

    setMessages((prev) => [
      ...prev,
      { role: "user", texte: question },
      { role: "assistant", texte: "" },
    ]);
    setSaisie("");
    setEnvoi(true);
    setStreamActif(true);
    setErreur(null);

    demarrerRevelation();

    try {
      await streamerClaude(apiBaseUrl, historiqueAvant, question, (chunk) => {
        // On accumule dans le buffer — le setInterval s'occupe du reveal.
        bufferRef.current += chunk;
      });
      streamTermineRef.current = true;
    } catch (e) {
      streamTermineRef.current = true;
      // Coupe immédiatement le reveal + retire la bulle vide si rien reçu
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      setStreamActif(false);
      setErreur(e instanceof Error ? e.message : t("chatbot.messageErreur"));
      setMessages((prev) => {
        const dernier = prev[prev.length - 1];
        if (dernier && dernier.role === "assistant" && dernier.texte === "") {
          return prev.slice(0, -1);
        }
        return prev;
      });
    } finally {
      setEnvoi(false);
    }
  }

  function surToucheClavier(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      envoyer();
    }
  }

  return (
    <>
      {/* Bouton flottant */}
      <button
        type="button"
        onClick={() => setOuvert((v) => !v)}
        aria-label={t("chatbot.bouton")}
        className="fixed bottom-5 right-5 z-[1200] flex items-center gap-2 rounded-full
                   bg-paa-navy-700 px-4 py-3 text-white shadow-lg
                   hover:bg-paa-navy-900 focus:outline-none focus:ring-2 focus:ring-paa-blue-400
                   transition-all"
      >
        <IconChatbot className="h-5 w-5" />
        <span className="hidden text-fluid-xs font-medium sm:inline">{t("chatbot.bouton")}</span>
      </button>

      {/* Fenêtre de chat */}
      {ouvert && (
        <div
          className="fixed bottom-20 right-5 z-[1200] flex w-[clamp(300px,90vw,420px)] flex-col
                     rounded-2xl border app-border bg-white shadow-2xl dark:bg-paa-navy-950"
          style={{ maxHeight: "70vh" }}
        >
          {/* En-tête */}
          <div className="flex items-center justify-between rounded-t-2xl bg-paa-navy-700 px-4 py-3">
            <div className="flex items-center gap-2 text-white">
              <IconChatbot className="h-5 w-5" />
              <span className="text-fluid-sm font-semibold">{t("chatbot.titre")}</span>
            </div>
            <button
              type="button"
              onClick={() => setOuvert(false)}
              aria-label={t("chatbot.fermer")}
              className="text-white/70 hover:text-white"
            >
              <IconClose className="h-5 w-5" />
            </button>
          </div>

          {/* Corps — messages */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3" style={{ minHeight: 0 }}>
            {messages.length === 0 && (
              <div className="space-y-3">
                <div className="rounded-2xl rounded-bl-sm bg-gray-100 px-3 py-2 text-fluid-xs leading-relaxed dark:bg-paa-navy-800 dark:text-paa-blue-100">
                  <p className="font-medium text-paa-navy-700 dark:text-paa-blue-200 mb-1">
                    👋 Bonjour ! Je suis le guide de FLUIDIS.
                  </p>
                  <p>
                    Je peux vous expliquer comment fonctionne l'application, vous aider à trouver la bonne page, ou répondre à vos questions sur les données de trafic portuaire.
                  </p>
                </div>
                <p className="text-fluid-xs app-text-muted px-1">Questions fréquentes :</p>
                <div className="flex flex-col gap-1.5">
                  {QUESTIONS_SUGGEREES.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => setSaisie(q)}
                      className="rounded-xl border border-paa-blue-300 bg-paa-blue-50 px-3 py-1.5
                                 text-left text-fluid-xs text-paa-navy-700 hover:bg-paa-blue-100
                                 dark:border-paa-navy-600 dark:bg-paa-navy-800/60 dark:text-paa-blue-200
                                 dark:hover:bg-paa-navy-700 transition-colors"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => {
              // On masque la bulle assistant vide (avant réception du 1er token)
              // — le voyant "…" ci-dessous prend le relais.
              if (msg.role === "assistant" && msg.texte === "") return null;

              // La dernière bulle assistant, tant que le stream est actif,
              // reçoit la classe chatbot-laser-typing (curseur + halo).
              const estStreamEnCours =
                streamActif
                && msg.role === "assistant"
                && i === messages.length - 1;

              return (
                <div
                  key={i}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-3 py-2 text-fluid-xs leading-relaxed whitespace-pre-wrap ${
                      msg.role === "user"
                        ? "bg-paa-navy-700 text-white rounded-br-sm"
                        : "bg-gray-100 text-paa-navy-900 dark:bg-paa-navy-800 dark:text-paa-blue-100 rounded-bl-sm"
                    } ${estStreamEnCours ? "chatbot-laser-typing" : ""}`}
                  >
                    {msg.texte}
                  </div>
                </div>
              );
            })}

            {envoi
              && messages[messages.length - 1]?.role === "assistant"
              && messages[messages.length - 1]?.texte === "" && (
              <div className="flex justify-start">
                <div className="rounded-2xl rounded-bl-sm bg-gray-100 px-3 py-2 text-fluid-xs app-text-muted dark:bg-paa-navy-800">
                  <span className="animate-pulse">…</span>
                </div>
              </div>
            )}

            {erreur && (
              <p className="text-fluid-xs text-red-500 px-1">{erreur}</p>
            )}

            <div ref={basRef} />
          </div>

          {/* Zone de saisie */}
          <div className="flex items-end gap-2 border-t app-border px-3 py-2">
            <textarea
              value={saisie}
              onChange={(e) => setSaisie(e.target.value)}
              onKeyDown={surToucheClavier}
              placeholder={t("chatbot.placeholder")}
              rows={1}
              disabled={envoi}
              className="flex-1 resize-none rounded-lg border app-border app-surface px-3 py-2
                         text-fluid-xs focus:outline-none focus:ring-2 focus:ring-paa-blue-400
                         disabled:opacity-50 min-h-[36px] max-h-24"
              style={{ fieldSizing: "content" } as React.CSSProperties}
            />
            <button
              type="button"
              onClick={envoyer}
              disabled={envoi || !saisie.trim()}
              aria-label={t("chatbot.envoyer")}
              className="flex-shrink-0 rounded-lg bg-paa-navy-700 px-3 py-2 text-white
                         hover:bg-paa-navy-900 disabled:opacity-40 transition-colors"
            >
              <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4" aria-hidden="true">
                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
              </svg>
            </button>
          </div>
        </div>
      )}
    </>
  );
}

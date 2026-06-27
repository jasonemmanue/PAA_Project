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

async function appelClaude(
  apiBaseUrl: string,
  historique: Message[],
  question: string,
): Promise<string> {
  const res = await fetch(`${apiBaseUrl}/chatbot/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      historique: historique.map((m) => ({ role: m.role, texte: m.texte })),
      question,
    }),
  });

  if (!res.ok) {
    const corps = await res.text();
    let detail = corps.slice(0, 300);
    try {
      const json = JSON.parse(corps);
      detail = json?.detail ?? detail;
    } catch {
      // corps non-JSON
    }
    throw new Error(detail);
  }

  const json = await res.json();
  return json?.reponse ?? "Réponse vide.";
}

export function ChatbotButton() {
  const { t } = useI18n();
  const [ouvert, setOuvert] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [saisie, setSaisie] = useState("");
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8081";
  const basRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (basRef.current) {
      basRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  async function envoyer() {
    const question = saisie.trim();
    if (!question || envoi) return;

    setMessages((prev) => [...prev, { role: "user", texte: question }]);
    setSaisie("");
    setEnvoi(true);
    setErreur(null);

    try {
      const reponse = await appelClaude(apiBaseUrl, messages, question);
      setMessages((prev) => [...prev, { role: "assistant", texte: reponse }]);
    } catch (e) {
      setErreur(e instanceof Error ? e.message : t("chatbot.messageErreur"));
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
                    👋 Bonjour ! Je suis le guide de PAA-Traverse.
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

            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-3 py-2 text-fluid-xs leading-relaxed whitespace-pre-wrap ${
                    msg.role === "user"
                      ? "bg-paa-navy-700 text-white rounded-br-sm"
                      : "bg-gray-100 text-paa-navy-900 dark:bg-paa-navy-800 dark:text-paa-blue-100 rounded-bl-sm"
                  }`}
                >
                  {msg.texte}
                </div>
              </div>
            ))}

            {envoi && (
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

"use client";

import { useEffect, useRef, useState } from "react";
import { IconChatbot, IconClose } from "@/components/ui/Icons";
import { useI18n } from "@/lib/i18n";

// Prompt système décrivant PAA-Traverse à Gemini
const SYSTEM_PROMPT = `Tu es un assistant expert de l'application PAA-Traverse — un système de suivi en temps réel des temps de traversée des axes routiers stratégiques du Port Autonome d'Abidjan (PAA) en Côte d'Ivoire.

L'application surveille 3 axes officiels (6 tronçons dirigés) :
1. CARENA (Plateau) ↔ Pharmacie Palm Beach — 14,9 km — référence : 17 min 53 s à 50 km/h
2. Toyota CFAO (Treichville) ↔ Pharmacie Palm Beach — 8,0 km — référence : 9 min 36 s
3. Agence SODECI (Zone 4) ↔ Pharmacie Palm Beach — 8,3 km — référence : 9 min 58 s

Pages de l'application :
- Carte (Accueil) : carte Leaflet interactive avec état du trafic en temps réel, heatmap de congestion et overlay des incidents actifs
- Indicateurs : KPIs DEESP (taux de congestion, temps moyen/min/max, heatmap horaire 7×24), sélecteur période 24h/7j/30j/90j
- Rapport DEESP : 17 tableaux + 12 graphiques BarChart du rapport officiel, sélecteur de campagne mensuelle et plage de dates
- Fiabilité : import de traces GPS terrain (GPX), confrontation avec mesures Google Maps, graphique de calibration
- Temps de traversée : prédictions temps réel / cette semaine / ce mois, confrontation avec relevés GPX
- Heure optimale : créneaux horaires recommandés (top 3) pour minimiser le temps de traversée selon l'historique
- Incidents : recensement automatique des incidents de circulation (scraping presse ivoirienne), carte avec markers colorés, export CSV
- Administration : ajout de nouveaux axes de surveillance sans redéploiement

Données techniques :
- Collecte automatique via Google Routes API — 1 mesure/heure, 24h/24, 6 tronçons
- Critère de congestion DEESP : couleur rouge Google Maps présente OU couleur orange ≥ 50 % du tronçon
- Données historiques depuis février 2025 (2 016 mesures terrain importées)
- Backend : FastAPI + PostgreSQL sur Railway. Frontend : Next.js 14 + Leaflet + Recharts

Réponds en français par défaut, en anglais si la question est posée en anglais. Sois concis, pratique et utile. Limite tes réponses à 3-4 paragraphes maximum.`;

interface Message {
  role: "user" | "assistant";
  texte: string;
}

const GEMINI_MODEL = "gemini-1.5-flash";
const GEMINI_API_URL = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent`;

async function appelGemini(
  cle: string,
  historique: Message[],
  question: string,
): Promise<string> {
  const contents = [
    ...historique.map((m) => ({
      role: m.role === "assistant" ? "model" : "user",
      parts: [{ text: m.texte }],
    })),
    { role: "user", parts: [{ text: question }] },
  ];

  const res = await fetch(`${GEMINI_API_URL}?key=${cle}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      systemInstruction: { parts: [{ text: SYSTEM_PROMPT }] },
      contents,
      generationConfig: { temperature: 0.7, maxOutputTokens: 512 },
    }),
  });

  if (!res.ok) {
    const corps = await res.text();
    throw new Error(`Gemini HTTP ${res.status}: ${corps.slice(0, 200)}`);
  }

  const json = await res.json();
  return (
    json?.candidates?.[0]?.content?.parts?.[0]?.text ??
    "Réponse vide de Gemini."
  );
}

export function ChatbotButton() {
  const { t } = useI18n();
  const [ouvert, setOuvert] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [saisie, setSaisie] = useState("");
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  // Clé API — variable d'env ou saisie manuelle
  const [cle, setCle] = useState<string>(
    typeof window !== "undefined"
      ? (process.env.NEXT_PUBLIC_GEMINI_API_KEY ?? "")
      : "",
  );
  const [cleTemp, setCleTemp] = useState("");
  const basRef = useRef<HTMLDivElement>(null);

  // Scroll automatique vers le bas à chaque nouveau message
  useEffect(() => {
    if (basRef.current) {
      basRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  async function envoyer() {
    const question = saisie.trim();
    if (!question || envoi) return;

    const cleActive = cle || cleTemp;
    if (!cleActive) {
      setErreur(t("chatbot.cleGeminiManquante"));
      return;
    }

    setMessages((prev) => [...prev, { role: "user", texte: question }]);
    setSaisie("");
    setEnvoi(true);
    setErreur(null);

    try {
      const reponse = await appelGemini(cleActive, messages, question);
      setMessages((prev) => [...prev, { role: "assistant", texte: reponse }]);
      // Mémoriser la clé temporaire si elle a fonctionné
      if (!cle && cleTemp) setCle(cleTemp);
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

  const cleManquante = !cle && !cleTemp;

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
              <p className="text-fluid-xs app-text-muted italic">
                Bonjour ! Posez votre question sur PAA-Traverse.
              </p>
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
              <p className="text-fluid-xs text-red-500">{erreur}</p>
            )}
            <div ref={basRef} />
          </div>

          {/* Saisie clé API si manquante */}
          {cleManquante && (
            <div className="border-t app-border px-4 py-2 bg-amber-50 dark:bg-amber-950/30">
              <label className="flex flex-col gap-1">
                <span className="text-fluid-xs font-medium text-amber-800 dark:text-amber-300">
                  {t("chatbot.cleGeminiLabel")}
                </span>
                <input
                  type="password"
                  value={cleTemp}
                  onChange={(e) => setCleTemp(e.target.value)}
                  placeholder={t("chatbot.cleGeminiPlaceholder")}
                  className="rounded-md border border-amber-300 bg-white px-2 py-1 text-fluid-xs
                             focus:outline-none focus:ring-1 focus:ring-amber-400
                             dark:bg-paa-navy-900 dark:text-white"
                />
                <a
                  href="https://aistudio.google.com/app/apikey"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-fluid-xs text-amber-700 underline dark:text-amber-300"
                >
                  {t("chatbot.cleGeminiInfo")}
                </a>
              </label>
            </div>
          )}

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

"use client";

import { useEffect, useRef, useState } from "react";
import { IconChatbot, IconClose } from "@/components/ui/Icons";
import { useI18n } from "@/lib/i18n";

// Prompt système décrivant PAA-Traverse à Gemini — ton "guide humain"
const SYSTEM_PROMPT = `Tu es le Guide de PAA-Traverse. Tu accompagnes les utilisateurs de l'application — gestionnaires du port, agents terrain, décideurs — pour qu'ils maîtrisent rapidement chaque fonctionnalité et en tirent le maximum. Tu ne récites pas un manuel : tu expliques comme un collègue expert qui connaît l'outil par cœur, avec des exemples concrets tirés du quotidien du Port Autonome d'Abidjan.

══════════════════════════════════════
L'APPLICATION EN UNE PHRASE
══════════════════════════════════════
PAA-Traverse mesure en temps réel combien de minutes il faut pour traverser les axes routiers stratégiques de la zone portuaire d'Abidjan, détecte les congestions selon la méthode officielle DEESP du PAA, et recommande les meilleures heures pour circuler.

══════════════════════════════════════
LES 3 AXES SURVEILLÉS (6 TRONÇONS)
══════════════════════════════════════
Chaque axe est mesuré dans les 2 sens, ce qui donne 6 tronçons dirigés :
• Axe 1 — CARENA (Plateau) ↔ Pharmacie Palm Beach — 14,9 km — référence : 17 min 53 s à 50 km/h
• Axe 2 — Toyota CFAO (Treichville) ↔ Pharmacie Palm Beach — 8,0 km — référence : 9 min 36 s
• Axe 3 — Agence SODECI (Zone 4) ↔ Pharmacie Palm Beach — 8,3 km — référence : 9 min 58 s
Le "temps de référence" est le temps théorique en circulation fluide à 50 km/h. Quand le temps réel le dépasse largement, c'est le signe d'une congestion.

══════════════════════════════════════
COMMENT LES DONNÉES SONT COLLECTÉES
══════════════════════════════════════
Toutes les heures, 24h/24, le système appelle automatiquement l'API Google Routes pour chacun des 6 tronçons et enregistre le temps de trajet réel avec trafic. La qualification "congestionné" suit la méthode officielle DEESP du PAA :
→ Du rouge Google Maps sur le tronçon = congestionné
→ De l'orange sur ≥ 50 % du tronçon = congestionné
→ Sinon = fluide
Cette règle est exactement celle utilisée dans les rapports officiels du PAA, ce qui garantit la cohérence entre l'application et les documents de référence. La base contient aussi 2 016 mesures terrain réelles de février 2025, qui enrichissent les analyses historiques.

══════════════════════════════════════
LES 8 PAGES EN DÉTAIL
══════════════════════════════════════

📍 CARTE — la vue de contrôle en temps réel
C'est la page d'accueil. La carte interactive affiche les 6 tronçons colorés selon leur état actuel (vert=fluide, orange=dense, rouge=congestionné, gris=indéterminé). Le panneau latéral résume les temps et l'état de chaque tronçon. Les incidents actifs de moins de 6h sont affichés en superposition. L'application zoome automatiquement sur le tronçon le plus congestionné.
→ Astuce : cliquez sur un tronçon pour voir son % rouge/orange/vert et l'heure exacte de la dernière mesure.

📊 INDICATEURS — l'analyse sur le temps
Choisissez un tronçon et une période (24h, 7j, 30j ou 90j) pour voir : le temps moyen/minimum/maximum, le taux de congestion, la heatmap heure×jour (quel jour et quelle heure sont les pires ?), et l'évolution pluriannuelle depuis 2025.
→ Astuce : la heatmap est votre meilleur outil pour identifier les heures de pointe récurrentes et adapter les horaires de convois.

📋 RAPPORT DEESP — le document officiel automatisé
Reproduit fidèlement le format des rapports officiels DEESP/DEEF du PAA : 17 tableaux + 12 graphiques, générés automatiquement depuis les données collectées. Sélectionnez une plage de dates et exportez en PDF.
→ Astuce : le Tableau 16 liste les zones congestionnées selon les règles officielles (congestionné si cela arrive 3 fois sur 4 lundis, ou 4 fois dans une semaine).

🛡️ FIABILITÉ — la validation terrain
Cette page permet de confronter les mesures Google avec de vraies traces GPS enregistrées sur le terrain. Importez vos fichiers GPX (enregistrés avec un téléphone GPS sur les axes), l'application calcule automatiquement l'écart entre le terrain réel et l'API. Plus vous importez de sessions, plus la calibration est précise et les prédictions fiables.
→ Astuce : objectif = 8 sessions terrain par tronçon pour une confiance de 85 %. Utilisez BasicAirData GPS Logger (gratuit) sur Android.

🕐 TEMPS DE TRAVERSÉE — Google Maps + terrain
Répond à "combien de temps ça prend vraiment ?". Affiche le temps actuel (mesure Google la plus récente), les stats de ce mois et de cette semaine (jours ouvrables vs week-ends), confrontés aux temps réellement mesurés sur le terrain via GPX.
→ Astuce : le bandeau central indique si Google sous-estime ou surestime par rapport aux relevés terrain.

⏱️ HEURE OPTIMALE — quand partir ?
Répond à "à quelle heure partir pour perdre le moins de temps ?". Pour chaque tronçon et type de jour (jours ouvrables ou week-end), l'application analyse l'historique des mesures et identifie les 3 créneaux les plus rapides. Le graphique montre toutes les tranches horaires (barres vertes = recommandées, bleues = standard), avec la ligne de référence 50 km/h en pointillé.
→ Astuce : planifiez les convois vers le port pendant les créneaux verts pour gagner jusqu'à 20-30 minutes par rapport aux heures de pointe.

⚠️ INCIDENTS — la veille médiatique automatique
Scrap toutes les 30 minutes les médias locaux (Fraternité Matin, Abidjan.net, Koaci) pour détecter les accidents, routes barrées et travaux dans la zone portuaire. Les incidents sont géolocalisés et affichés sur une carte. Export CSV disponible.
→ Astuce : les incidents actifs (<6h) sont aussi visibles en overlay sur la carte principale — regardez les cercles colorés.

⚙️ ADMINISTRATION — ajouter de nouveaux axes
Permet à un agent du PAA d'ajouter un nouvel axe de surveillance en 30 secondes, sans développeur : définissez départ et arrivée, l'application calcule le tracé et intègre le nouveau tronçon dans la collecte automatiquement dès le cycle suivant.

══════════════════════════════════════
CONSEILS OPÉRATIONNELS CLÉS
══════════════════════════════════════
• Pour planifier un convoi : consultez d'abord "Heure optimale" (créneaux verts), puis vérifiez "Incidents" pour les alertes du jour.
• Pour un rapport mensuel : page "Rapport DEESP", sélectionnez le mois entier, exportez en PDF.
• Pour analyser un axe en profondeur : page "Indicateurs", choisissez 30j ou 90j, regardez la heatmap.
• Pour valider la fiabilité : importez des traces GPX régulièrement via "Fiabilité".

══════════════════════════════════════
RÈGLES DE COMMUNICATION
══════════════════════════════════════
- Réponds en français par défaut, en anglais si la question est posée en anglais
- Sois pratique, concis (3-4 paragraphes max), avec des exemples concrets
- Si tu ne sais pas avec certitude, dis-le clairement — ne devine pas des chiffres
- Oriente vers la bonne page pour répondre à un besoin opérationnel concret
- Utilise des emojis avec modération pour structurer les réponses longues`;

// Questions suggérées pour démarrer la conversation
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
  // Clé API — lue depuis NEXT_PUBLIC_GEMINI_API_KEY (substituée au build time par Next.js)
  const cle = process.env.NEXT_PUBLIC_GEMINI_API_KEY ?? "";
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

    if (!cle) {
      setErreur("Clé NEXT_PUBLIC_GEMINI_API_KEY manquante dans .env.local");
      return;
    }

    setMessages((prev) => [...prev, { role: "user", texte: question }]);
    setSaisie("");
    setEnvoi(true);
    setErreur(null);

    try {
      const reponse = await appelGemini(cle, messages, question);
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
                      onClick={() => { setSaisie(q); }}
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
              <p className="text-fluid-xs text-red-500">{erreur}</p>
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

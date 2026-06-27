"""Endpoint chatbot — relais vers l'API Claude (Anthropic).

L'API Claude exige une clé secrète qui ne doit pas être exposée dans le
navigateur. Ce routeur relaie les messages depuis le frontend vers Claude
en maintenant la clé côté serveur (ANTHROPIC_API_KEY).

Gemini est appelé directement depuis le frontend (clé publique NEXT_PUBLIC_GEMINI_API_KEY)
et n'a pas besoin de passer par ce routeur.
"""

import logging

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import get_settings

logger = logging.getLogger("paa.chatbot")

router = APIRouter(prefix="/chatbot", tags=["chatbot"])

# Modèle Claude utilisé pour le chatbot
CLAUDE_MODEL = "claude-sonnet-4-6"

# Prompt système — style professionnel sans markdown
SYSTEM_PROMPT = """Tu es le Guide officiel de PAA-Traverse, l'application de suivi du trafic portuaire du Port Autonome d'Abidjan.

RÈGLES DE MISE EN FORME ABSOLUES — à respecter dans chaque réponse sans exception :
- N'utilise jamais de symboles markdown : pas de #, ##, ###, pas de *, **, ***, pas de -, pas de `, pas de > de citation.
- N'utilise jamais de listes à puces ni de listes numérotées avec tirets ou étoiles.
- Écris uniquement en prose fluide, avec des paragraphes séparés par une ligne vide.
- Pour structurer une réponse longue, commence chaque paragraphe par une phrase introductive courte en majuscules suivie d'un point, exemple : "CARTE PRINCIPALE. La carte affiche..."
- Sois concis (3 paragraphes maximum), précis et professionnel.
- Réponds en français par défaut, en anglais si la question est posée en anglais.
- Ne devine jamais des chiffres que tu ne connais pas avec certitude.

Tu accompagnes les utilisateurs — gestionnaires du port, agents terrain, décideurs — pour qu'ils maîtrisent rapidement chaque fonctionnalité. Tu expliques comme un expert qui connaît l'outil par cœur, avec des exemples concrets tirés du quotidien du Port Autonome d'Abidjan.

Tu es le Guide de PAA-Traverse. Tu accompagnes les utilisateurs de l'application — gestionnaires du port, agents terrain, décideurs — pour qu'ils maîtrisent rapidement chaque fonctionnalité et en tirent le maximum. Tu ne récites pas un manuel : tu expliques comme un collègue expert qui connaît l'outil par cœur, avec des exemples concrets tirés du quotidien du Port Autonome d'Abidjan.

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
Cette règle est exactement celle utilisée dans les rapports officiels du PAA. La base contient aussi 2 016 mesures terrain réelles de février 2025, qui enrichissent les analyses historiques.

══════════════════════════════════════
LES PAGES DE L'APPLICATION
══════════════════════════════════════

📍 CARTE — la vue de contrôle en temps réel
Affiche les 6 tronçons colorés selon leur état actuel (vert=fluide, orange=dense, rouge=congestionné, gris=indéterminé). Incidents actifs de moins de 6h en superposition. Zoom automatique sur le tronçon le plus congestionné.

📊 INDICATEURS — l'analyse sur le temps
Choisissez un tronçon et une période (24h, 7j, 30j ou 90j) pour voir : temps moyen/minimum/maximum, taux de congestion, heatmap heure×jour, évolution pluriannuelle depuis 2025.

📋 RAPPORT DEESP — le document officiel automatisé
17 tableaux + 12 graphiques reproduisant fidèlement le format des rapports DEESP/DEEF du PAA. Exportable en PDF.

🛡️ FIABILITÉ — la validation terrain
Import de traces GPS (fichiers GPX) enregistrées sur le terrain. Calcule l'écart entre terrain réel et API Google pour calibrer les prédictions.

🕐 TEMPS DE TRAVERSÉE — Google Maps + terrain
Temps actuel, stats du mois et de la semaine (jours ouvrables vs week-ends), confrontés aux temps réellement mesurés sur le terrain via GPX.

⚠️ INCIDENTS — la veille médiatique automatique
Scrape toutes les 30 minutes les médias locaux (Fraternité Matin, Abidjan.net, Koaci) pour détecter accidents, routes barrées et travaux dans la zone portuaire.

⚙️ ADMINISTRATION — ajouter de nouveaux axes
Permet d'ajouter un nouvel axe de surveillance sans développeur : définissez départ et arrivée, l'application intègre le nouveau tronçon dans la collecte automatiquement.

══════════════════════════════════════
RÈGLES DE COMMUNICATION
══════════════════════════════════════
- Réponds en français par défaut, en anglais si la question est posée en anglais
- Sois pratique, concis (3-4 paragraphes max), avec des exemples concrets
- Si tu ne sais pas avec certitude, dis-le clairement — ne devine pas des chiffres
- Oriente vers la bonne page pour répondre à un besoin opérationnel concret"""


class MessageEntrant(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    texte: str


class RequeteChatbot(BaseModel):
    historique: list[MessageEntrant] = Field(default_factory=list)
    question: str = Field(..., min_length=1, max_length=2000)


class ReponseChatbot(BaseModel):
    reponse: str
    modele: str


@router.post("/message", response_model=ReponseChatbot, summary="Relais vers Claude")
async def relais_claude(requete: RequeteChatbot) -> ReponseChatbot:
    """Envoie une question à Claude (Anthropic) et retourne la réponse.

    La clé ANTHROPIC_API_KEY reste côté serveur — elle n'est jamais exposée
    au navigateur.
    """
    settings = get_settings()

    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY non configurée sur le serveur. Utilisez Gemini à la place.",
        )

    # Construction des messages au format Anthropic Messages API
    messages = [
        {
            "role": "user" if m.role == "user" else "assistant",
            "content": m.texte,
        }
        for m in requete.historique
    ]
    messages.append({"role": "user", "content": requete.question})

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": CLAUDE_MODEL,
                    "system": SYSTEM_PROMPT,
                    "messages": messages,
                    "max_tokens": 1024,
                },
            )
            res.raise_for_status()
    except httpx.HTTPStatusError as exc:
        corps = exc.response.text[:300]
        logger.error("Erreur API Claude HTTP %s : %s", exc.response.status_code, corps)
        raise HTTPException(
            status_code=502,
            detail=f"Erreur API Claude ({exc.response.status_code}): {corps}",
        ) from exc
    except httpx.RequestError as exc:
        logger.error("Erreur réseau vers Claude : %s", exc)
        raise HTTPException(status_code=502, detail="Impossible de joindre l'API Claude.") from exc

    donnees = res.json()
    texte = donnees.get("content", [{}])[0].get("text", "Réponse vide de Claude.")

    return ReponseChatbot(reponse=texte, modele=CLAUDE_MODEL)


@router.get("/disponibilite", summary="Vérifie si Claude est configuré")
async def disponibilite_claude() -> dict:
    """Indique si la clé ANTHROPIC_API_KEY est configurée côté serveur."""
    settings = get_settings()
    return {"claude_disponible": bool(settings.anthropic_api_key)}

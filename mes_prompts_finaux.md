# Prompts restants — réalignement DEESP/DEEF

> Ce document remplace les sections **9 (Phase 6)** et **10 (Phase 7)** du guide
> *« Guide__Hackathon_PAA_Process.docx »*. Chaque prompt a été récrit pour
> s'aligner sur la méthodologie officielle DEESP/DEEF du rapport
> *« Évaluation du temps de traversée — octobre 2025 »* (cf. [CLAUDE.md § 4.5](CLAUDE.md)).
>
> **Différences clés vs le guide original** :
>
> - Indicateurs DEESP (min/moyen/max + jours-ouvrables vs week-ends) priment
>   sur FHWA dans les vues métier
> - Collecte horaire (1 mesure/heure entre 7h et 19h) au lieu de 15 min
> - Critère congestion : ratio > 1,5 × T_ref (équivalent rouge/orange-long Google Maps)
> - Règles d'occurrence du rapport : ≥ 3/jour-indicatif ou ≥ 4/semaine
> - Tableau de bord publique = **Rapport DEESP** avec ses 17 tableaux + 12 BarCharts
> - La page Indicateurs (FHWA) reste pour le monitoring temps réel

---

## Sommaire des prompts restants

| Prompt | Phase | Objet | Réalisé ? |
|--------|-------|-------|-----------|
| 6.2 | Phase 6 — Prédicteur | Prédicteur DEESP par profils horaires + cascade dégradée | ⏳ À faire |
| 6.3 | Phase 6 — Heure optimale | Module « quand partir pour arriver à l'heure ? » | ⏳ À faire |
| 6.4 | Phase 6 — Administration | Ajout dynamique de tronçons + sous-tronçons codifiés (T1A, T1B…) | ⏳ À faire |
| 6.5 | Phase 6 — ML (optionnel) | Random Forest avec évaluation honnête vs prédicteur niveau 2 | ⏳ Optionnel |
| 7.1 | Phase 7 — Tests | Tests fonctionnels + cache Redis + optimisations | ⏳ À faire |
| 7.2 | Phase 7 — Déploiement | Frontend Vercel (backend Railway déjà OK) | ⏳ À faire |
| 7.3 | Phase 7 — Pitch | Rapport final article 4 + trame de pitch | ⏳ À faire |

---

## ⌨ PROMPT 6.2 — Prédicteur interne aligné DEESP + cascade de repli

### 🎯 Rôle de ce prompt

Ce prompt construit le prédicteur interne qui fonctionne hors ligne, sans
Google. Avec les données déjà collectées par la sonde horaire (cf. §4.5.1)
et les 2 016 mesures terrain de février 2025 (`source=historique_paa_2025`),
le prédicteur est immédiatement pertinent.

**Spécificité DEESP** : le prédicteur publie ses résultats dans le format
attendu par le rapport — `min_mn`, `moyen_mn`, `max_mn` par type-jour
(jour ouvrable vs week-end), pas en TTI/PTI/BTI.

La cascade de repli (Google → prédicteur DEESP → temps de référence 50 km/h)
garantit qu'aucune réponse n'est vide — démontrable au jury en coupant
Google volontairement.

### 📎 À joindre à Claude Code

Aucun document à joindre (CLAUDE.md § 4.5 sert de référence).

### Prompt à copier-coller

```
CONTEXTE
Phase 6 (J14–J16). La base contient :
  - les mesures horaires courantes (source=google) depuis migration 0001
  - les 2 016 mesures de février 2025 (source=historique_paa_2025) via import 6.1
  - les profils horaires agrégés chaque nuit dans profils_horaires (fenêtres 30/60/90 jours)

Méthodologie DEESP (cf. CLAUDE.md § 4.5) :
  - on raisonne en minutes (pas en secondes pour l'affichage utilisateur)
  - on distingue jour_ouvrable (lundi-vendredi) vs week_end (samedi-dimanche)
  - on publie 3 valeurs : min / moyen / max
  - le critère "congestionné" est : duree_trafic_s > 1.5 × T_ref_50kmh

TÂCHES
1. Backend : nouveau module app/predicteur/profils.py
   - Fonction predire(troncon_id, instant_local, fenetre_jours=60) qui :
     a) interroge profils_horaires pour (troncon_id, instant.weekday(), instant.hour, fenetre_jours)
     b) si profils présents : retourne {min_mn, mediane_mn, p95_mn, moyenne_mn, max_mn}
     c) applique une pondération exponentielle 0.9^k selon l'ancienneté en semaines
     d) multiplie par le facteur de calibration courant (depuis /terrain/calibration)
     e) ajoute le type_jour (jour_ouvrable/week_end) calculé depuis weekday
     f) ajoute la source utilisée et le degré de confiance (0..1)

2. Cascade de dégradation gracieuse (refactor de app/etat/carte.py et endpoints existants)
   Pour TOUTE demande de temps de traversée future ou actuelle, suivre l'ordre :
     1. Google Routes si disponible et instant proche du présent (±15 min)
     2. Prédicteur DEESP (profils historiques pondérés)
     3. Temps de référence 50 km/h calculé depuis distance_m
   Chaque réponse DOIT inclure le champ "source" indiquant le niveau de la cascade.

3. Endpoint GET /predire
   Query params : troncon_id (int), date (YYYY-MM-DD), heure (0..23, optionnel défaut="auto")
   Réponse JSON :
   {
     "troncon_id": 1,
     "troncon_nom": "CARENA (Plateau) → Pharmacie Palm Beach",
     "instant_local": "2026-06-22T08:00:00+00:00",
     "type_jour": "jour_ouvrable",
     "prediction": {
       "min_mn": 18,
       "moyen_mn": 24,
       "max_mn": 32,
       "fourchette_p25_p75_mn": [21, 28],
       "p95_mn": 30
     },
     "source": "predicteur_profils_60j",
     "confiance": 0.87,
     "calibration_appliquee": -0.043
   }

4. Endpoint GET /predire/qualite
   Renvoie la MAE du prédicteur calculée sur les 7 derniers jours (mesures Google
   réelles vs prédictions), en minutes.

5. Alertes de congestion anormale
   Quand une mesure courante dépasse le P95 historique du créneau correspondant,
   créer une entrée dans une nouvelle table alertes :
     id, troncon_id, horodatage_utc, valeur_mesuree_s, p95_attendu_s, type_jour, lu
   Migration Alembic 0006_alertes.

6. Frontend : ajouter une page /prediction
   - Sélecteur de tronçon
   - Sélecteur date (input date, par défaut aujourd'hui)
   - Sélecteur heure (slider 0..23, défaut = heure courante locale Africa/Abidjan)
   - Bouton "Prédire"
   - Affichage en 3 cartes : Min / Moyen / Max en gros (minutes)
   - Sous-titre : "Basé sur N mesures historiques (jour ouvrable / week-end)"
   - Badge source (vert si "google_routes", bleu si "predicteur_profils_60j",
     gris si "vitesse_ref_50kmh")
   - Phrase d'interprétation auto-générée :
     "Pour un trajet le mardi 22/06 à 08h00, comptez en moyenne 24 minutes
      (entre 18 et 32 minutes selon les conditions)."

RENDU ATTENDU
1. GET /predire?troncon_id=1&date=2026-06-22&heure=8 renvoie une prédiction réaliste
2. Si on retire GOOGLE_ROUTES_API_KEY temporairement, /predire continue de répondre
   en utilisant la source "predicteur_profils_60j"
3. La page /prediction affiche les 3 valeurs Min/Moyen/Max formatées en minutes
4. Test démonstratif : prédire à 8h un jour ouvrable et à 8h un dimanche pour
   le même tronçon, observer la différence (jour_ouvrable ≠ week_end)

CONTRAINTES
- Toutes les durées affichées à l'utilisateur sont en MINUTES (rapport DEESP)
- Distinction systématique jour_ouvrable / week_end
- Le calibration_appliquee vient de la moyenne mobile des écarts terrain (P5)
- Aucune utilisation directe de TTI/PTI/BTI dans cette page
```

---

## ⌨ PROMPT 6.3 — Heure optimale de départ vers le port (aligné DEESP)

### 🎯 Rôle de ce prompt

Ce prompt répond à la question concrète du transporteur :
**« quand partir pour arriver au port au mieux ? »**.
C'est la transposition à coût nul des systèmes de rendez-vous camions
documentés à Hambourg, Los Angeles et Manille.

**Spécificité DEESP** : les recommandations distinguent **jours ouvrables**
et **week-ends** comme dans le rapport. La propagation temporelle (appliquer
à chaque tronçon le profil de l'heure où le véhicule l'atteindra réellement)
reste le détail qui rend la recommandation crédible.

### 📎 À joindre à Claude Code

Aucun document à joindre.

### Prompt à copier-coller

```
CONTEXTE
Phase 6. Le prédicteur DEESP (6.2) est en place. On veut désormais répondre :
"Pour partir de [point X] et arriver à la Pharmacie Palm Beach,
 quelle heure dois-je choisir aujourd'hui (ou jour J) ?"

TÂCHES
1. Backend — Endpoint GET /heure-optimale
   Query params :
     - depart (string)        : nom de lieu géocodable OU "lat,lon"
     - destination (string)   : pour l'instant "port" (résolu en Palm Beach)
     - date (YYYY-MM-DD)      : jour visé
     - heure_arrivee (optionnel): contrainte "doit arriver avant HH:MM"
     - tronçon_id (optionnel) : si l'utilisateur veut forcer un axe d'arrivée

2. Logique de calcul (app/predicteur/heure_optimale.py)
   a) Géocoder le point de départ via Nominatim (api gratuit OpenStreetMap)
   b) Si tronçon_id non fourni : identifier le tronçon dont l'origine est la
      plus proche du géocode (Haversine sur les 6 tronçons actifs).
   c) Approche libre : appeler OSRM /route pour la durée du trajet
      [depart → origine_du_troncon]. Cette durée est constante pour la journée
      (pas de données trafic en dehors des 6 tronçons surveillés).
   d) Pour chaque créneau de départ par pas de 30 min entre 7h et 19h :
      - calculer instant_arrivee_au_troncon = creneau_depart + approche_libre
      - PROPAGATION TEMPORELLE : prédire le temps de traversée via /predire
        pour cet instant précis (donc le profil horaire utilisé est celui
        de l'heure d'arrivée au tronçon, pas de l'heure de départ)
      - calculer temps_total_mn = approche_libre_mn + traversee_predite_mn
   e) Identifier le créneau optimal (min temps_total_mn) et le pire créneau
      (max temps_total_mn)
   f) Distinguer jour_ouvrable vs week_end dans la réponse

3. Format de réponse
   {
     "depart": {"adresse": "...", "lat": ..., "lon": ...},
     "troncon_utilise": {"id": 3, "nom": "Toyota CFAO → Palm Beach"},
     "date": "2026-06-22",
     "type_jour": "jour_ouvrable",
     "approche_libre_mn": 12,
     "creneaux": [
       {"depart": "07:00", "arrivee_troncon": "07:12", "traversee_mn": 22, "total_mn": 34},
       {"depart": "07:30", "arrivee_troncon": "07:42", "traversee_mn": 28, "total_mn": 40},
       ...
       {"depart": "19:00", "arrivee_troncon": "19:12", "traversee_mn": 14, "total_mn": 26}
     ],
     "creneau_optimal": {"depart": "10:00", "total_mn": 24, "gain_vs_pire_mn": 16},
     "creneau_pire": {"depart": "08:00", "total_mn": 40},
     "recommandation": "Partez entre 09h30 et 10h30 ce mardi : vous gagnez ≈ 16 min par rapport à 08h00."
   }

4. Frontend — page /prediction enrichie avec onglet "Heure optimale"
   - Bandeau d'entrée : champ "point de départ" (autocomplete Nominatim) +
     date (input date)
   - Bouton "Calculer la meilleure heure"
   - Carte centrée sur le départ avec marker + tracé OSRM jusqu'à l'origine
     du tronçon proposé
   - BarChart Recharts : axe X = créneau de départ, axe Y = temps total mn,
     bar dorée pour le créneau optimal, bar rouge pour le pire
   - Encadré "Notre recommandation" avec la phrase auto-générée
   - Badge "Calculé pour un jour ouvrable / week-end"

RENDU ATTENDU
1. Pour un départ "Plateau, Abidjan" un jeudi : graphique des 25 créneaux
   et recommandation textuelle chiffrée
2. Démonstration jour-ouvrable vs week-end pour le MÊME point :
   les recommandations diffèrent

CONTRAINTES
- Toutes les durées affichées : MINUTES entières (rapport DEESP)
- Distinguer jour_ouvrable vs week_end dans le rendu
- Si OSRM indisponible : approche_libre estimée par distance Haversine ÷ 30 km/h
  (vitesse urbaine moyenne hors zone portuaire)
- Si Nominatim indisponible : permettre lat,lon direct en fallback
```

---

## ⌨ PROMPT 6.4 — Administration : ajout dynamique de tronçons + sous-tronçons codifiés

### 🎯 Rôle de ce prompt

Exigence explicite du cahier des charges et du rapport DEESP. Ce prompt
permet à un agent du PAA d'ajouter un tronçon en 30 secondes, **sans
développeur**, et de **subdiviser un axe en sous-tronçons codifiés**
(T1A, T1B, T1C…) comme le fait la DEESP pour son analyse fine des zones
de congestion.

**Spécificité DEESP** : le rapport oct. 2025 attribue des codes à des
sous-portions des 3 axes (cf. Tableau 16 et conclusion). Notre app doit
permettre cette granularité sans casser la collecte des axes principaux.

### 📎 À joindre à Claude Code

Aucun document à joindre.

### Prompt à copier-coller

```
CONTEXTE
Phase 6. La méthodologie DEESP (CLAUDE.md § 4.5) introduit la notion de
sous-tronçons codifiés (T1A, T1B, T1C, T2A, T2B, ..., T3C) qui sont des
portions des 3 axes principaux. Cela permet une analyse fine des zones
de congestion (Tableau 16 du rapport).

Modèle de données à étendre :
- troncons garde son rôle actuel (6 axes dirigés)
- nouvelle table sous_troncons (parent troncon, code, polyline portion, ordre)
- mesures peut pointer optionnellement sur un sous_troncon (FK nullable)

TÂCHES (backend)

1. Migration Alembic 0007_sous_troncons
   - Table sous_troncons :
     id (PK), troncon_id (FK), code (str 10 ex "T1A"), nom_court (str 100),
     ordre (int, séquence sur le tronçon parent),
     lat_debut, lon_debut, lat_fin, lon_fin,
     polyline (text), distance_m (int), actif (bool default true)
   - Index unique (troncon_id, code), index (troncon_id, ordre)

2. Modèle SQLAlchemy SousTroncon + relation Troncon.sous_troncons

3. Endpoints REST
   POST /troncons : création d'un axe principal
     body: { nom, lat_origine, lon_origine, lat_destination, lon_destination,
             waypoints?: [[lat, lon]], vitesse_ref_kmh? (default 50), couleur? }
     → appelle OSRM /route, stocke polyline + distance_m
     → renvoie le tronçon créé
   PATCH /troncons/{id} : modifie nom, couleur, vitesse_ref_kmh
   DELETE /troncons/{id} : suppression LOGIQUE (actif=false), conserve l'historique

   POST /troncons/{id}/sous-troncons : créer un sous-tronçon
     body: { code, nom_court, lat_debut, lon_debut, lat_fin, lon_fin, ordre }
     → appelle OSRM pour calculer la polyline+distance entre les deux points
     → vérifie que les 2 extrémités tombent dans le buffer (200 m) de la
       polyline du tronçon parent
   GET /troncons/{id}/sous-troncons : liste ordonnée
   DELETE /sous-troncons/{id} : suppression logique

4. Modifier le scheduler de collecte
   - Le collecteur continue de mesurer les 6 axes principaux comme avant
   - Pour chaque mesure du parent, ajouter un calcul OSRM des durées de
     CHACUN de ses sous-tronçons via /route segmenté (1 requête OSRM par
     sous-tronçon ; on garde le quota Google car ces appels sont OSRM, pas Google)
   - Insertion d'une mesure liée au sous_troncon_id

5. Modifier l'analyse rapport_paa (CLAUDE.md § 4.5)
   La fonction troncons_congestionnes() prend désormais en compte les
   sous-tronçons s'ils sont définis : un sous-tronçon est congestionné si
   son ratio (sous_troncon.duree / sous_troncon.t_ref_50_kmh) > 1.5

6. Endpoint GET /rapport/sous-troncons-congestionnes?campagne=AAAA-MM
   → renvoie la même structure que /rapport/zones-congestionnees mais à la
     granularité sous-tronçon (Tableau 16 du rapport DEESP)

TÂCHES (frontend, page /administration)

7. Sélecteur d'onglet : "Axes principaux" / "Sous-tronçons"

8. Onglet Axes principaux
   Étape 1 : champ "nom" + 2 clics sur la carte (marker vert = origine,
             marker rouge = destination)
             OU saisie nom de lieu (autocomplete Nominatim)
   Étape 2 : à la définition des 2 extrémités, appel POST OSRM → carte
             affiche le tracé en pointillés violets (prévisualisation)
             + encart avec distance + temps de référence 50 km/h
   Étape 3 (optionnelle) : ajout de waypoints intermédiaires par clic
             pour refléter l'itinéraire camion (OSRM recalcule)
   Étape 4 : bouton "Valider" → POST /troncons → tronçon ajouté

9. Onglet Sous-tronçons
   - Sélecteur de tronçon parent (les 6 axes)
   - Carte affichant la polyline du parent en gras
   - Au clic, l'utilisateur place 2 markers (début et fin) du sous-tronçon
   - Champ code (texte court "T1A", autocomplete des codes utilisés sur cet axe)
   - Champ nom_court
   - Bouton "Valider" → POST /troncons/{id}/sous-troncons
   - Liste des sous-tronçons existants en bas, avec leur code et leur état
     (actif/archivé) + bouton suppression logique

RENDU ATTENDU
1. Démonstration : ajouter un nouvel axe "AGL → Grand Moulin" par 2 clics
   sur la carte + bouton Valider. Recharger /troncons : il apparaît.
2. Démonstration : sur l'axe CARENA → Palm Beach, ajouter 3 sous-tronçons
   T1A (CARENA → début du pont), T1B (pont), T1C (sortie pont → Palm Beach).
3. Au cycle de collecte suivant (60 min plus tard ou via endpoint
   POST /collecte/run-once) :
   - le nouvel axe reçoit sa première mesure Google
   - les 3 sous-tronçons reçoivent leur mesure OSRM
4. /rapport/sous-troncons-congestionnes?campagne=AAAA-MM montre les
   sous-tronçons congestionnés par tranche horaire (granularité fine du rapport)

CONTRAINTES
- Suppression TOUJOURS logique (actif=false) — exigence cahier des charges
- Le tronçon nouvellement ajouté est inclus AU PROCHAIN CYCLE sans
  redémarrage du scheduler
- Les sous-tronçons ne consomment PAS de quota Google (calculés via OSRM)
- Format des codes : T<n_axe><lettre> (T1A, T1B, T2A, T3A...) — convention DEESP
```

---

## ⌨ PROMPT 6.5 — ML Random Forest avec évaluation honnête (optionnel)

### 🎯 Rôle de ce prompt

Ce prompt n'est rentable que grâce aux 2 016 mesures de février 2025.
La règle d'or à présenter au jury : **le modèle ML n'est promu que s'il
bat le prédicteur niveau 2 sur la MAE**, sinon on garde le niveau 2.
Cette honnêteté méthodologique est un argument de crédibilité, pas une
faiblesse.

**Spécificité DEESP** : les variables d'entrée et la métrique de comparaison
sont exprimées en **minutes** pour rester cohérent avec le rapport.

### 📎 À joindre à Claude Code

Aucun document à joindre (données de février déjà en base).

### Prompt à copier-coller

```
CONTEXTE
Phase 6 niveau 3 (optionnel). Le prédicteur niveau 2 (profils horaires)
fonctionne déjà. On teste si un ML peut faire mieux.

Données disponibles :
- 2 016 mesures terrain de février 2025 (source=historique_paa_2025)
- mesures Google horaires depuis migration 0001 (taille variable selon
  l'ancienneté du déploiement)

TÂCHES

1. Module app/predicteur/ml.py
   - Pipeline scikit-learn :
     features = ["heure_sin", "heure_cos",
                 "jour_semaine_sin", "jour_semaine_cos",
                 "troncon_id" (one-hot),
                 "is_week_end" (0/1),
                 "is_saison_pluies" (juin-octobre, 0/1),
                 "lag_30_mn" (mesure 30 min plus tôt, NaN si absent),
                 "lag_60_mn" (1h plus tôt)]
     target = duree_trafic_mn

2. Découpage train/test STRICTEMENT TEMPOREL (jamais aléatoire)
   - train : du 01/02/2025 au 20/02/2025
   - test  : du 21/02/2025 au 28/02/2025

3. Modèles essayés :
   - RandomForestRegressor (n_estimators=200)
   - HistGradientBoostingRegressor

4. Évaluation : MAE en minutes
   - Calculer MAE_niveau_2 (prédicteur profils) sur le même test set
   - Calculer MAE_niveau_3 (ML) sur le test set
   - Tableau final : MAE en minutes pour chaque type_jour, par axe

5. Règle de promotion
   if MAE_ml < MAE_profil * 0.90:   # gain ≥ 10 % requis
       PREDICTEUR_RETENU = "ml"
       persister le modèle dans models/predicteur_ml.joblib
   else:
       PREDICTEUR_RETENU = "profils"
       afficher honnêtement les deux MAE

6. Endpoint GET /predire/qualite renvoie :
   {
     "predicteur_actif": "profils" ou "ml",
     "mae_minutes": {
       "predicteur_profils": {"jour_ouvrable": 4.2, "week_end": 3.1},
       "predicteur_ml":      {"jour_ouvrable": 5.8, "week_end": 3.4}
     },
     "date_evaluation": "2026-06-21",
     "decision": "Niveau 2 retenu — Random Forest ne bat pas les profils horaires."
   }

7. Frontend — petit encart en bas de la page /prediction
   - Tableau des MAE
   - Phrase explicite : "Notre prédicteur retenu est le [niveau 2 / niveau 3].
     Précision moyenne ± 4,2 minutes sur les jours ouvrables."

RENDU ATTENDU
1. Tableau comparatif MAE niveau 2 vs niveau 3 affiché honnêtement
2. Le choix est cohérent avec les chiffres (le modèle promu est bien
   celui qui gagne)
3. Endpoint /predire/qualite renvoie la décision

CONTRAINTES
- Aucune triche : si le ML perd, on le dit
- Métrique = MAE en minutes (rapport DEESP), pas RMSE en secondes
- Split temporel jamais aléatoire (sinon biais énorme)
```

---

## ⌨ PROMPT 7.1 — Tests fonctionnels + cache Redis + optimisations

### 🎯 Rôle de ce prompt

Phase 7 (J19). Avant le pitch, on stabilise : tests automatisés, cache,
chargement paresseux. Tous les endpoints critiques doivent rester < 200 ms
sous une charge raisonnable.

**Spécificité DEESP** : les tests incluent **explicitement** la validation
des règles méthodologiques (ratio 1.5 pour congestion, comptage ≥3/jour-
indicatif ou ≥4/semaine, distinction jour_ouvrable/week_end).

### 📎 À joindre à Claude Code

Aucun document à joindre.

### Prompt à copier-coller

```
CONTEXTE
Phase 7. Avant le pitch, on stabilise et on optimise.

TÂCHES (tests automatisés)

1. tests/test_rapport_paa.py
   - test_temps_theoriques_retourne_3_axes()
   - test_congestion_seuil_15_classe_correctement()  # cas limite ratio=1.49 et 1.51
   - test_regle_3_jour_indicatif_appliquee_correctement()  # mock 4 lundis
   - test_regle_4_semaine_appliquee_correctement()  # mock 4 jours distincts
   - test_distinction_jour_ouvrable_week_end()  # samedi vs lundi
   - test_collecte_horaire_144_req_par_jour()  # quota Google estimé : 24 cycles × 6 tronçons

2. tests/test_predicteur.py
   - test_cascade_google_predicteur_50kmh()  # mock chaque niveau
   - test_predicteur_renvoie_min_moyen_max()  # format DEESP
   - test_calibration_terrain_appliquee()  # avec un facteur connu

3. tests/test_terrain_p5.py (existant à enrichir)
   - test_decoupage_GPX_detecte_les_6_troncons()
   - test_appariement_google_dans_fenetre_30_min()

4. Configuration pytest + fixture DB de test (SQLAlchemy + alembic upgrade)
   - Use SQLite in-memory pour les tests unitaires
   - Use postgres docker compose pour les tests d'intégration

TÂCHES (cache Redis)

5. app/cache.py : wrapper Redis avec TTL configurable
   - cache_carte_etat (TTL 60 s) : /carte/etat ne refait pas la query SQL
     dans la même minute
   - cache_rapport_temps_traversee (TTL 5 min, key = (campagne, hash_troncons))
   - cache_predire (TTL 10 min, key = (troncon_id, instant_local arrondi à
     30 min))
   - invalidation automatique : à chaque insertion dans mesures, supprimer
     les clés cache_carte_etat et cache_predire concernées

TÂCHES (optimisations frontend)

6. Lazy loading des composants lourds
   - CarteLeaflet : déjà dynamic import, vérifier les chunks Next.js
   - Recharts : import dynamic avec ssr:false des wrappers BarChart/LineChart
   - leaflet.heat : import seulement sur la page Accueil/Carte

7. Compression API
   - Backend : middleware gzip Brotli si dispo
   - Frontend : next.config.js compress: true

8. Audit Lighthouse
   - Score perf ≥ 80 sur la page Carte en mobile
   - Score accessibilité ≥ 90

TÂCHES (responsive final)

9. Tests visuels manuels sur les 3 breakpoints (375, 768, 1024 px)
   pour chaque page : Accueil, Indicateurs, Rapport, Fiabilité, Prédiction,
   Administration. Capture d'écran de chacune pour la doc finale.

RENDU ATTENDU
1. pytest tests/ passe avec 0 échec
2. /carte/etat répond en < 50 ms (cache chaud)
3. Lighthouse desktop ≥ 90, mobile ≥ 80 sur la page Carte
4. 18 captures d'écran (6 pages × 3 breakpoints) classées dans docs/screenshots/
5. Rapport bref des optimisations appliquées dans docs/optimisations.md

CONTRAINTES
- Tests d'intégration utilisent un docker compose dédié (compose.test.yml)
- Le cache invalide TOUJOURS les clés concernées à chaque écriture
- Lighthouse 80 mobile est non-négociable (cible cahier des charges)
```

---

## ⌨ PROMPT 7.2 — Déploiement public (Vercel frontend + Railway backend)

### 🎯 Rôle de ce prompt

Le backend tourne déjà sur Railway (cf. CLAUDE.md § 8.2). Ce prompt
finalise le **déploiement du frontend Next.js sur Vercel** et configure
les variables de production. Optionnellement, on bascule OSRM sur Oracle
Cloud (cf. CLAUDE.md § 8.7) si la procédure n'est pas encore réalisée.

### 📎 À joindre à Claude Code

Aucun document à joindre.

### Prompt à copier-coller

```
CONTEXTE
Phase 7. Le backend FastAPI tourne sur Railway depuis le 2026-06-19
(https://backend-production-6cbf.up.railway.app). PostgreSQL et Redis
sont des plugins Railway. Reste à déployer le frontend Next.js.

État de OSRM (cf. CLAUDE.md § 8.3 et § 8.7) :
- Soit OSRM est sur Oracle Cloud Free Tier ⇒ OSRM_BASE_URL est défini sur Railway
- Soit OSRM n'est pas exposé ⇒ on tourne en mode best-effort (polylines
  segments droits via complete_sans_osrm)

TÂCHES

1. Déploiement Vercel du frontend
   a) Connecter le repo GitHub à Vercel via la console Vercel
   b) Configurer le projet :
      - Root directory : frontend/
      - Framework preset : Next.js (auto-détecté)
      - Build command : npm run build
      - Output directory : .next (default)
   c) Variables d'environnement Vercel (Production) :
      - NEXT_PUBLIC_API_BASE_URL=https://backend-production-6cbf.up.railway.app
      - NEXT_PUBLIC_DEFAULT_LANG=fr
   d) Déclencher un déploiement
   e) Noter l'URL Vercel (du type https://paa-traverse-frontend.vercel.app)

2. Mise à jour CORS côté Railway
   a) Ajouter l'URL Vercel à ALLOWED_ORIGINS :
      railway variables --set \
        "ALLOWED_ORIGINS=https://paa-traverse-frontend.vercel.app,http://localhost:3000,http://localhost:3030" \
        --service backend

3. Validation production
   a) Ouvrir l'URL Vercel
   b) Vérifier les 6 pages : Carte, Indicateurs, Rapport, Fiabilité,
      Prédiction, Administration
   c) Vérifier l'inspecteur réseau : tous les appels XHR/fetch vont vers
      l'URL Railway, pas localhost
   d) Vérifier que la WebSocket /ws/etat se connecte (badge "● temps réel"
      en haut à droite de la carte)
   e) Tester l'upload d'un GPX via /fiabilite
   f) Tester /rapport avec le mois courant

4. Documentation
   Mettre à jour CLAUDE.md § 8.1 (architecture cible) avec l'URL Vercel
   finale. Mettre à jour README.md § 7.1 (URL publique) avec un encadré
   "Déploiement actif" et les deux URL (frontend Vercel + backend Railway).

5. Bonus — si OSRM Oracle Cloud pas encore en place
   Optionnel : suivre la procédure CLAUDE.md § 8.7 pour exposer OSRM
   en permanence. Une fois fait, lancer sur Console Railway :
     railway variables --set "OSRM_BASE_URL=https://votre-osrm.example.org"
     python -m app.complete_troncons
   pour avoir les vraies polylines routières sur la carte de prod.

RENDU ATTENDU
1. URL publique Vercel fonctionnelle : toutes les pages chargent
2. Réseau valide : appels API vers Railway, WebSocket connectée
3. CLAUDE.md + README.md mis à jour avec les URLs finales

CONTRAINTES
- Aucun secret committé dans le repo (vérifier .gitignore avant tout push)
- Variables d'environnement de prod uniquement dans les consoles Vercel/Railway
- Pas de Storage Vercel utilisé (les uploads GPX restent côté Railway BYTEA)
```

---

## ⌨ PROMPT 7.3 — Rapport final article 4 + trame de pitch (alignement DEESP)

### 🎯 Rôle de ce prompt

Dernier prompt. Produit le rapport reprenant point par point **l'article 4
du cahier des charges** ET le **rapport DEESP de référence**, et structure
le pitch. Le jury est institutionnel : la trame *problème → existant
mondial → vide local → solution → démo live → impact chiffré* est celle
qui convainc.

**Spécificité DEESP** : le rapport final doit **revendiquer explicitement**
l'alignement avec la méthodologie DEESP/DEEF (§ 4.5 de CLAUDE.md). C'est
la preuve que notre outil n'est pas une démo générique mais l'outillage
numérique du processus officiel du PAA.

### 📎 À joindre à Claude Code

**À JOINDRE** :
- Le rapport DEESP d'octobre 2025 (.docx) — pour aligner le vocabulaire
- La note explicative du cahier des charges si disponible
- Les 18 captures d'écran produites en 7.1

### Prompt à copier-coller

```
CONTEXTE
Phase 7 finale. On produit le livrable jury.

TÂCHES

1. Rapport final docs/rapport-final.md
   Structure :
   a) Introduction (1 page)
      - Rappel du contexte PAA (40 millions de tonnes/an, 78 % recettes
        douanières, etc.)
      - Le besoin : suivi temps réel + analyse historique du temps de traversée
   b) Méthodologie (2 pages)
      - Alignement explicite avec le rapport DEESP/DEEF d'octobre 2025
      - Tableau de correspondance article 4 ↔ écran applicatif
      - 5 indicateurs DEESP + critère ratio 1.5 + règles 3/4
      - Distinction jour_ouvrable / week_end
   c) Architecture technique (1 page)
      - Schéma : Frontend Vercel ← Backend Railway ← Postgres + Redis +
        OSRM Oracle (le cas échéant) + Google Routes API
      - Cascade de dégradation gracieuse (Google → prédicteur → 50 km/h)
   d) Réponses aux 6 résultats attendus de l'article 4
      Pour chacun : (i) le résultat attendu (cité textuellement), (ii)
      l'écran/endpoint qui y répond, (iii) une capture d'écran insérée.
      Les 6 résultats :
      1) Base de données fiable des temps de traversée temps réel
      2) Analyse du niveau de congestion par tronçon et par créneau
      3) Identification des zones de congestion récurrentes
      4) Évolution de l'indicateur "temps de traversée"
      5) Cartographie des congestions (échelle couleurs, heatmap)
      6) Recommandations opérationnelles
   e) Conformité au rapport DEESP (1 page)
      - Tableau : « Notre app reproduit fidèlement les 17 tableaux et 12
        graphiques du rapport DEESP » avec lien vers chaque écran
      - Démonstration : page /rapport reproduit Tableau 16
        (tronçons congestionnés) avec les règles 3/4 officielles
   f) Validation terrain (1 page)
      - Page Fiabilité : import GPX, calcul ε, calibration
      - Honnêteté : les GPX actuels sont synthétiques, à remplacer par
        de vrais relevés (mode simulation documenté § 4.3.1)
   g) Recommandations opérationnelles (extraites du rapport DEESP)
      Les 5 recommandations finales du rapport, reprises avec notre
      contribution :
      1. Programmation et appel des camions ⇒ notre /heure-optimale
         répond à ce besoin
      2. Relocalisation cités résidentielles ⇒ hors scope app
      3. Délocalisation SICTA ⇒ hors scope app
      4. Réparation asphaltage ⇒ hors scope app
      5. Système d'alerte temps réel ⇒ NOTRE app
   h) Coût (1 page)
      - Backend Railway : ~5 $/mois en plan Pro
      - Frontend Vercel : 0 $/mois en Hobby tier
      - OSRM Oracle Cloud Free Tier : 0 $/mois permanent
      - Google Routes : 0 $/mois (sous le quota 250 req/jour)
      - **TOTAL : ~5 $/mois pour un outil opérationnel**

2. Pitch de 5-7 minutes (docs/pitch.md)
   Trame :
   (1) Le problème — 30 sec
       "Les congestions du port d'Abidjan coûtent X minutes par camion par jour"
   (2) L'existant mondial — 30 sec
       "Hambourg smartPORT, Los Angeles PierPass, Manille TABS : tous ces
        ports ont mis en place des systèmes de rendez-vous et de prédiction"
   (3) Le vide local — 30 sec
       "Le PAA a la méthodologie (rapport DEESP) mais pas l'outillage
        numérique. Notre application est exactement cet outillage."
   (4) Notre solution — 1 min 30 s
       - Carte temps réel (live demo)
       - Page Rapport DEESP avec ses 17 tableaux (live demo)
       - Heure optimale de départ (live demo)
       - Validation terrain GPX (montrer la page)
   (5) Démo live — 2 min
       - Ouvrir / : voir les 6 tronçons colorés
       - Cliquer sur un tronçon : popup avec TTI, source, dernière mesure
       - Aller sur /rapport : tableau 16 affiche les zones congestionnées
       - **Tour de magie** : sur Railway, débrancher GOOGLE_ROUTES_API_KEY,
         puis aller sur /prediction. L'app continue de répondre avec la
         source "predicteur_profils_60j". Reconnecter Google ⇒ la source
         redevient "google_routes". C'est la cascade gracieuse en action.
   (6) Impact et coût — 1 min
       - Économies par camion par jour
       - Coût total 5 $/mois
       - Ouvert sur les axes futurs : ajout dynamique sans dev (démo
         live sur /administration si le temps le permet)
   (7) Q&A — temps restant

3. 7 facteurs de démarcation à insérer dans le pitch
   - Double source de mesure (Google + GPX terrain)
   - Cascade de dégradation gracieuse (jamais de réponse vide)
   - Validation terrain scientifique (page Fiabilité)
   - Indicateurs FHWA en plus de DEESP
   - Heure optimale de départ avec propagation temporelle
   - Actif de données propriétaire (2 016 mesures fév 2025 + mesures
     horaires courantes)
   - Coût quasi nul (~5 $/mois)

4. Mettre à jour CLAUDE.md
   - Section finale "État final livré au jury" avec checklist verte
   - Lien vers docs/rapport-final.md et docs/pitch.md
   - Tableau de conformité DEESP : 17 tableaux + 12 graphiques tous mappés

RENDU ATTENDU
1. docs/rapport-final.md (~15 pages) prêt à imprimer
2. docs/pitch.md avec timing minute par minute
3. CLAUDE.md final avec checklist de jury
4. Démo répétée 2 fois en mode "tour de magie" (couper Google et continuer)

CONTRAINTES
- Le vocabulaire DEESP/DEEF doit être utilisé partout (jour_ouvrable,
  temps minimal/moyen/maximal en minutes, ratio 1.5, règles 3/4)
- Aucune référence visible à des bibliothèques ou outils techniques dans
  le pitch oral — uniquement la valeur métier
- Les chiffres mentionnés doivent être SOURCÉS (DEESP, Banque mondiale,
  ITF, etc.) — on ne sort jamais un chiffre sans pouvoir le justifier
```

---

## Annexe — Récapitulatif des prompts restants

| Prompt | Objet | Statut | Document à joindre |
|--------|-------|--------|--------------------|
| 6.2 | Prédicteur DEESP (min/moy/max en minutes) | ⏳ À faire | Aucun |
| 6.3 | Heure optimale de départ | ⏳ À faire | Aucun |
| 6.4 | Admin + sous-tronçons codifiés (T1A, T1B…) | ⏳ À faire | Aucun |
| 6.5 | ML Random Forest (optionnel) | ⏳ Optionnel | Aucun |
| 7.1 | Tests + Cache Redis + Optimisations | ⏳ À faire | Aucun |
| 7.2 | Déploiement Vercel | ⏳ À faire | Aucun |
| 7.3 | Rapport final + Pitch | ⏳ À faire | Rapport DEESP + captures |

### Ordre d'exécution recommandé

```
6.2 → 6.3 → 6.4 → (6.5 optionnel) → 7.1 → 7.2 → 7.3
```

### Validation après chaque prompt

À chaque prompt, vérifier :
- ✅ Le RENDU ATTENDU est concrètement vérifiable (endpoint qui répond,
  écran qui s'affiche)
- ✅ Les CONTRAINTES sont respectées (DEESP : minutes, jour-ouvrable/week-end)
- ✅ Un test fonctionnel manuel passe (ex. /predire répond, /heure-optimale
  retourne le bon créneau)
- ✅ Commit Git après validation

### Conventions DEESP rappelées à chaque prompt

| Convention | Forme |
|------------|-------|
| Durées affichées | **minutes entières** (jamais secondes) |
| Distinction temporelle | jour_ouvrable (lun-ven) vs week_end (sam-dim) |
| Indicateurs publiés | min / moyen / max (pas TTI/PTI/BTI dans l'UI rapport) |
| Critère congestion | duree > 1.5 × T_ref_50_kmh |
| Règles d'occurrence | ≥ 3/jour-indicatif OU ≥ 4/semaine |
| Fréquence collecte | 1 mesure / heure 7h–19h |
| Format codes sous-tronçons | T1A, T1B, T1C, T2A, … |

---

## Bon hackathon !

Exécutez les prompts dans l'ordre, validez chaque livrable, committez après
chaque étape. La méthodologie DEESP/DEEF du PAA est votre fil rouge : ne
vous en éloignez jamais, c'est elle qui donne au prototype sa **légitimité
opérationnelle** face au jury institutionnel.

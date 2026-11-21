# CLAVERATS Pro - Suite SaaS d'Audit Sémantique CV, Recrutement RH & Intelligence Géographique

Application web Full-Stack développée avec **Python (Flask)**, **OpenCV**, **pypdf**, **openpyxl**, **BeautifulSoup4** et **ReportLab**. Conçue avec une interface moderne Bento UI (Mode Clair & Mode Sombre), elle offre un double espace **Candidat** et **Équipe RH** fonctionnant **100 % en local (zéro stockage externe, confidentialité totale)**.

---

## Fonctionnalités Clés (Version Pro)

### 1. Module Candidat & Smart Parsing Multimodal
* **Entrées multi-formats :** Importation directe de CV et d'offres en **PDF** (lecture en mémoire vive), extraction depuis une **URL en ligne** ou collage de texte brut.
* **Vision par ordinateur locale (OpenCV) :** Détection automatique du visage et recadrage en avatar RH circulaire.
* **Analyse sémantique illimitée :** Extraction de **100 % des compétences** demandées par l'offre (Hard & Soft Skills + synonymes, sans plafond), estimation de séniorité (*Junior, Confirmé, Senior*) et détection de la posture dominante (*Analytique, Managériale, Opérationnelle*).
* **Simulateur Multi-Offres (Matrice de Chance) :** Comparaison simultanée de **2 à 4 offres d'emploi** pour classer les postes selon le taux de réussite technique, la proximité géographique et la tension du marché.
* **Optimiseur "ATS-Ready" & Impact Rédactionnel :** Audit technique du fichier PDF (texte extractible, structure des rubriques, longueur), détection des verbes d'action et des chiffres clés.
* **Double Calendrier Stratégique & Checklist Interactive :**
  * Widget semaine glissante avec indice de réactivité recruteur et calendrier mensuel distinguant les **jours ouverts (vert)** et les **dates optimales recommandées (orange)**.
  * **Checklist avant envoi (`0/4` → `4/4`)** avec barre de progression dynamique et message de confirmation pour postuler, export Agenda `.ICS` et lettre de motivation PDF.
* **Préparation d'Entretien Chronométrée :** Simulateur de questions probables avec minuteur de **90 secondes** (méthode STAR) et bloc-notes local.

### 2. Module RH & Aide à la Décision Visuelle
* **Bulk Upload (jusqu'à 50 CV) & Détection de Doublons :** Importation groupée de CV PDF avec classement instantané, graphiques de performance de cohorte et alerte automatique sur les candidatures en double.
* **Tableau de Suivi & Panneau Sombre Master-Detail :** Vue interactive combinant un tableau filtrable (avatar, nom, expérience, adresse, contact, niveau de score *Élevé / Moyen / Petit*) et une fiche détaillée 360° à droite.
* **Anonymisation Instantanée (RGPD) :** Interrupteur de floutage CSS dynamique masquant les photos, noms, adresses et contacts pour un tri 100 % objectif basé sur les compétences.
* **Comparateur 360° (Side-by-Side) :** Duel côte à côte entre 2 candidats avec **Graphique Radar 5 axes** et barres comparatives.
* **Générateur d'Entretien Prédictif & Scorecard PDF :** Détection des trous chronologiques (> 6 mois) et compétences manquantes, avec exportation du guide `.txt` et d'une **grille de notation PDF imprimable**.

### 3. Automatisation des Communications & Rapports
* **Rapport d'Audit Excel Avancé (`.xlsx`) :** Exportation instantanée de la shortlist RH vers un classeur Excel formaté (`openpyxl`) incluant scores, séniorité, posture, trajet, CO₂ et contacts.
* **Communication WhatsApp Souveraine :** Génération directe de liens `wa.me` avec message d'invitation pré-rempli et coordonnées du candidat.
* **Combobox de Gestion des Calendriers :** Liste déroulante sauvegardée en local permettant de mémoriser et d'insérer à la volée différents liens de rendez-vous RH.

### 4. Intelligence Géographique & Analyse du Marché Local
* **Carte de Densité des Candidatures :** Visualisation interactive des candidats par ville avec filtrage instantané au clic.
* **Calculateur de Distance, Trajet & Empreinte Carbone :** Estimation de la distance domicile-travail, du temps de trajet et de l'impact annuel en **kg de CO₂**.
* **Audit d'Attractivité du Marché :** Alerte automatique en cas d'incohérence entre les exigences de l'offre et les standards salariaux locaux.

### 5. Carte interactive hors-ligne (nouveau)
* **Relief & profondeur :** océan en dégradé, ombre portée sous les terres, halo côtier, grille latitude/longitude avec tropiques, vignette.
* **Interactions :** survol et clic sur les régions, zoom fluide (boutons, Ctrl + molette, double-clic, pincement), déplacement par glisser, marqueurs animés par ville, étiquettes sans chevauchement, trajet Vous → Offre avec distance.
* **Accessibilité :** marqueurs = vrais boutons (Tab / Entrée), clavier sur la carte (flèches, + / −, 0, Échap), annonces pour lecteurs d'écran, `prefers-reduced-motion` respecté.
* **Vrais pays (optionnel, automatique) :** l'application télécharge elle-même les frontières (Natural Earth, domaine public) en arrière-plan à la première connexion Internet et crée `static/data/world.geojson` (module `services/world_data.py`). Plus aucune commande manuelle ; `tools/fetch_world.py` reste disponible en secours hors-ligne. Sans Internet, la carte simplifiée intégrée est utilisée.

---

## Stack Technique

* **Backend :** Python 3, Flask, `pypdf`, `opencv-python-headless`, `numpy`, `Pillow`, `openpyxl`, `requests`, `BeautifulSoup4`, `ReportLab`
* **Frontend :** HTML5, CSS3 (Bento UI, Thème Clair/Sombre, Floutage RGPD), JavaScript Vanilla (Fetch API, LocalStorage)
* **Icônes :** Ionicons v2.0.0 (hébergé localement, zéro dépendance CDN)

---

## Structure du Projet

text
analyseur_cv_ats/
├── app.py                   # Serveur Flask, NLP, OpenCV, Géo, Excel & PDF
├── requirements.txt         # Dépendances Python du projet
├── INSTALLATION.txt         # Guide d'installation pas-à-pas
├── README.md                # Documentation complète
├── static/
│   ├── css/
│   │   ├── style.css        # Feuille de style Bento UI (Mode Clair & Sombre)
│   │   └── geomap.css       # Thème clair/sombre, relief et interactions de la carte
│   ├── js/
│   │   ├── main.js          # Logique interactive, graphiques, RGPD & exports
│   │   ├── geomap.js        # Carte interactive 100 % locale (zoom, survol, marqueurs, trajet)
│   │   └── geo-data.js      # Contours simplifiés des continents, îles, RD Congo et villes de référence
│   ├── data/
│   │   └── world.geojson    # (optionnel) vrais pays Natural Earth, créé par tools/fetch_world.py
│   └── libs/
│       └── ionicons/        # Bibliothèque d'icônes locale
├── tools/
│   └── fetch_world.py       # Télécharge une fois les frontières des pays (optionnel)
└── templates/
    └── index.html           # Interface Candidat & Espace Équipe RH


---

## Installation et Lancement en Local

1. **Installer les dépendances :**
   bash
   python -m pip install -r requirements.txt

2. **Démarrer le serveur :**
   bash
   python app.py


3. **Ouvrir dans le navigateur :**
   Accédez à **`http://127.0.0.1:5002`**.

---

## Auteur

**Glodi-Placide Oleko Diomba**  
Développeur Web & Solutions Numériques

---

## Version 2.1 - Services locaux, PWA et sécurité

**100 % local, sans base de données** : stockage exclusivement en fichiers JSON (`data/store/`), validés par empreinte SHA-256, écriture atomique, copie `.bak` automatique, sauvegardes rotatives (`data/backups/`), restauration et détection de corruption. LocalStorage = préférences et reprise de session. Aucune API externe n'est nécessaire (les 3 vérifications « en ligne » - DNS/SSL, GitHub - sont optionnelles et dégradent proprement hors-ligne).

### Dossier `services/` (modules autonomes, sans dépendance à Flask)
| Module | Rôle |
|---|---|
| `pdf_vision_extractor` | photo (cascade OpenCV + heuristiques anti-logo/QR), liens réels `/Annots→/URI`, nom strict, PDF chiffrés, OCR local optionnel |
| `contact_extractor` | e-mails, téléphones normalisés (081… → +243 81…), classification LinkedIn/GitHub/portfolio |
| `experience_analyzer` | durée exacte par expérience, trous, chevauchements, stabilité |
| `org_verifier` | type d'organisation (agence/direct), TLD suspect, punycode, préfixe téléphonique, DNS/SSL optionnels |
| `document_trust_analyzer`, `document_validator`, `document_security_engine`, `security_manager` | validation PDF (`%PDF-`, 15 Mo, JS), anti-SSRF, CSRF, rate-limit, PIN, neutralisation formules Excel, anonymisation |
| `profile_enricher` | liens du CV (+ GitHub public optionnel) |
| `interview_intelligence_engine` (= `ai_interview_engine`), `interview_manager` | TF-IDF/cosinus, questions STAR, notation de réponses, suivi d'entretiens |
| `ats_scoring` | score initial vs corrigé, lisibilité ATS |
| `talent_intelligence_engine`, `candidate_potential_analyzer`, `career_path_simulator`, `career_recommender`, `skills_gap_analyzer`, `skill_relationship_engine`, `job_knowledge_base` | profil de talent, potentiel, trajectoires, écarts, graphe de compétences |
| `recruitment_decision_engine`, `recruitment_scenario_engine`, `team_compatibility_engine`, `talent_discovery_engine`, `workforce_simulator`, `recruitment_analytics_engine`, `organizational_intelligence` | décision explicable, « et si », équipe, recherche, simulation d'embauche, analytique (entonnoir, podium, heatmap) |
| `candidate_history_manager`, `candidate_deduplication` (= `candidate_deduplicator`), `campaign_manager`, `application_tracker`, `data_manager`, `audit_trail_manager`, `report_generator` | historique/évolution, doublons, campagnes JSON, suivi, sauvegardes, journal chaîné, rapports |

L'onglet **Intelligence locale** (barre latérale) expose tout cela : *Mon profil*, *Vivier RH*, *Suivi & historique*, *Centre de contrôle* (santé des données, sauvegarde/restauration, PIN, purge, effacement total, journal d'audit).

### PWA
`static/manifest.json`, `static/sw.js` (`CACHE_VERSION = "claverats-v2.1"`), bandeau « nouvelle version », bouton d'installation. `/api/*` n'est jamais mis en cache. Fonctionne sur `localhost` / `127.0.0.1` ou HTTPS.

### Tests
`cd tests && python -m unittest discover -p "test_*.py"` (les tests utilisent un dossier temporaire, jamais vos données).

### Sécurité (résumé)
En-têtes (CSP, X-Frame-Options, nosniff…), jeton CSRF sur tous les POST, limitation de débit, `debug=False`, PDF validé en mémoire (jamais écrit sur disque), SHA-256 anti-doublon, limite d'image Pillow, échappement HTML côté Python et JS.

### Lieu : pays seul, ville absente (v2.1)
`services/geo_resolver.py` : si le CV ou l'offre ne donne que le pays (« RDC », « Pays : Cameroun »), la carte place un point approximatif libellé « (pays seulement) », **aucune distance n'est inventée** (même pays = 75 % « ville non précisée », pays différents = 35 % avec distance approximative). Sans aucun lieu, le pays est déduit d'un téléphone **à indicatif international** (+243…), signalé « à confirmer ». Les villes restent prioritaires sur les pays, et « Bénin » n'est plus confondu avec la ville de Beni.


## Nouveautés v2.2

* **Score dynamique** : compétences réellement exigées par l'employeur + référentiel du métier détecté (Informaticien, Infirmier, PAB…) ; explication, niveau de fiabilité, critère de lisibilité du CV. Bruit éliminé (« D », « etc. », « des »…).
* **Référentiels éditables** (onglet *Référentiels*) : `data/config/skills_referentials.json` - compétences, coefficients (×1/×2/×3), mots-clés/synonymes, nouveaux métiers.
* **Lieux robustes** : « RDC » ≡ « République démocratique du Congo », « Kinshasa, RDC » ≡ « RDC, Kinshasa » ≡ « Kinshasa » ; villes différentes d'un même pays = 60 %.
* **OCR local** des CV en JPG/PNG et des PDF scannés (Tesseract + OpenCV/Pillow) ; si Tesseract est absent, message clair et collage de texte.
* **Édition de l'offre** (entreprise, e-mail, lien, description) puis nouvelle analyse ; correction du retour en arrière des compétences modifiées.
* **Progression de carrière 1/3/5 ans** (indicative, règles expliquées, échelles modifiables dans `data/config/career_ladders.json`).
* **Historique** : suppression d'une analyse ou de tout l'historique (avec confirmation).
* **Mobile-first** : menu burger, accordéons repliés dans *Nouvelle analyse*, tableaux en cartes, aucun débordement horizontal (testé 360/414/768/1280 px).
* **Centre d'alertes RH** (doublons, dossiers incomplets, aucun candidat compatible, vivier de secours, scores proches, score peu fiable).

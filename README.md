# ATSMatcher Pro — Suite SaaS d'Audit Sémantique CV & Offres d'Emploi

Application web Full-Stack développée avec **Python (Flask)**, **pypdf**, **BeautifulSoup4** et **ReportLab**. Conçue avec une interface moderne multi-onglets (Mode Clair & Mode Sombre), elle analyse la compatibilité entre un CV et une offre d'emploi tout en évaluant la réalité terrain (éligibilité géographique, fiabilité de l'adresse e-mail recruteur, délais et cohérence rédactionnelle), le tout **100 % en local (zéro stockage externe)**.

---

## Fonctionnalités clés

* **Entrées multi-formats :**
  * **CV :** Importation directe d'un fichier **PDF** (lecture en mémoire vive) ou collage de texte brut.
  * **Offre d'emploi :** Importation d'un fichier **PDF**, extraction automatique depuis un **lien URL en ligne** ou collage du texte de l'annonce.
* **Interface SaaS Multi-Onglets & Thème Noir/Blanc :**
  * **5 onglets dédiés :** *Nouvelle Analyse*, *Vue d'ensemble*, *Profil & Vérification*, *Entretien & Audit CV* et *Candidature*.
  * **Profil candidat dynamique :** Extraction automatique du nom complet, des initiales et de la localisation affichés dans la barre supérieure.
  * **Mode Sombre / Mode Clair :** Bascule instantanée avec mémorisation automatique.
* **Analyse d'éligibilité géographique universelle :** Comparaison dynamique entre la ville/pays du candidat et le lieu de l'offre avec détection des clauses de télétravail (*Remote*) et de mutation/relocalisation (**100 % Éligible**, **50 % de chance si mutation non précisée**, ou **Éliminatoire**).
* **Audit de fiabilité de l'e-mail recruteur :** Vérification automatique du domaine de messagerie et des préfixes RH (`rh@`, `recrutement@`, `careers@`) avec indicateur de confiance (**100 % Certifié RH** vs **50 % Vigilance**).
* **Correction manuelle & Vérification croisée en temps réel :** Possibilité de modifier le nom, le lieu, l'expérience, le diplôme ou les langues extraites avec contrôle instantané de cohérence sur le texte brut du CV et recalcul du score global.
* **Simulateur d'entretien & Générateur de candidature :** Génération de questions probables d'entretien, audit de structure ATS du CV, checklist avant envoi, message de candidature prêt à copier et exportation d'un bilan professionnel en **PDF** (`ReportLab`).

---

## Stack Technique

* **Backend :** Python 3, Flask (API REST), `pypdf`, `requests`, `BeautifulSoup4`, `ReportLab`
* **Frontend :** HTML5, CSS3 (Grid/Flexbox, Variables CSS Thème Clair/Sombre), JavaScript Vanilla (Fetch API, FormData)
* **Icônes :** Ionicons v2.0.0 (hébergé localement, zéro dépendance CDN)

---

## Structure du projet

```text
analyseur_cv_ats/
├── app.py                   # Serveur Flask, moteur NLP, géographie, audit RH & PDF
├── requirements.txt         # Dépendances Python du projet
├── INSTALLATION.txt         # Guide d'installation pas-à-pas en français
├── .gitignore               # Fichiers exclus du suivi Git
├── README.md                # Documentation technique
├── static/
│   ├── css/
│   │   └── style.css        # Feuille de style SaaS (Mode Clair & Mode Sombre)
│   ├── js/
│   │   └── main.js          # Navigation par onglets, vérification directe & export PDF
│   └── libs/
│       └── ionicons/        # Bibliothèque d'icônes locale (CSS & Fonts)
└── templates/
    └── index.html           # Interface utilisateur principale (5 onglets)
```

---

## Installation et lancement en local

1. **Cloner le dépôt :**
   ```bash
   git clone https://github.com
   cd analyseur-cv-ats
   ```

2. **Installer les dépendances :**
   ```bash
   python -m pip install -r requirements.txt
   ```

3. **Démarrer le serveur :**
   ```bash
   python app.py
   ```

4. **Ouvrir dans le navigateur :**
   Accédez à **`http://127.0.0.1:5002`**.

---

## Auteur

**Glodi-Placide Oleko Diomba**  
Développeur Web & Solutions Numériques

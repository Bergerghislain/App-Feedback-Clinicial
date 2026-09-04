# Arcane - Format de presentation compatible IHU Prism

> Document de presentation structure selon un format academique/innovation sante: **Contexte -> Objectifs -> Methode -> Resultats -> Limites -> Roadmap -> Gouvernance**.

## 1) Identite projet

- **Nom projet:** Arcane Clinical Feedback Platform  
- **Repository source:** `Bergerghislain/App-Feedback-Clinicial`  
- **Nature:** Outil desktop d'evaluation clinique de conclusions IA/RCP  
- **Maturite actuelle:** Prototype operationnel terrain (collecte locale CSV)

## 2) Contexte

Le projet adresse un besoin d'evaluation clinique structuree de recommandations produites par:
- une source IA,
- une source RCP (reference humaine),
dans un contexte de comparaison blindee pour limiter le biais de jugement.

## 3) Probleme cible

- Absence d'outil simple pour evaluer de facon reproductible la pertinence clinique d'une conclusion.
- Necessite de capturer a la fois:
  - la qualite des conclusions,
  - la qualite de la reflexion explicative IA.

## 4) Objectifs

1. Permettre une evaluation blindee A/B de deux conclusions.
2. Capturer un score structure + un retour qualitatif clinicien.
3. Produire des exports exploitables en analyse statistique.
4. Simplifier l'usage terrain (lancement sans saisie complexe).

## 5) Methode / implémentation

### 5.1 Pipeline donnees
1. Chargement auto de `data.zip` (AES) via cle app obfusquee.
2. Detection des triplets `patient + evaluation RCP + evaluation IA`.
3. Presentation blindee des conclusions en `A/B`.
4. Collecte en 2 etapes:
   - Step 1: notation conclusions (1..5),
   - Step 2: QCM + commentaire sur reflexion IA.
5. Export CSV par domaine metier.

### 5.2 Stack technique
- Python 3.x
- PyQt6 (UI)
- pyzipper (zip AES)
- CSV/JSON (stockage local)

### 5.3 Securite appliquee
- `data.zip` chiffre AES.
- Mot de passe obfusque dans `.data_access.key`.
- Extraction temporaire nettoyee a la fermeture.
- Nouveau flux de recuperation cle: `recover-key`.

## 6) Resultats atteints

- Application exécutable localement.
- UX clinicien en 2 etapes complete.
- Progression reprenable (draft).
- Exports CSV metier generes automatiquement.
- Outils admin de packaging/dechiffrement/recovery disponibles.

## 7) Limites actuelles

- Monolithe unique (`app.py`) couplant UI et logique metier.
- Pas de tests automatiques formels.
- Pas d'API centralisee ni persistence serveur.
- Securite "pragmatique" mais non enterprise-grade.

## 8) Axes d'amelioration

- Refactor modulaire + tests unitaires.
- Validation schema JSON stricte.
- CI de build/lint/tests.
- Clarification nomenclature (correction orthographe "Clinicial" -> "Clinical").
- Eventuelle evolution vers architecture serveur (si besoin multi-sites).

## 9) Nomenclature recommandee pour transfert IHU Prism

Pour "emboiter parfaitement" une presentation institutionnelle:

1. **README** avec sections fixes:
   - Contexte
   - Objectifs
   - Methode
   - Resultats
   - Roadmap
   - Gouvernance
2. **docs/** avec:
   - `ARCANE_PROJET_DEEP_DIVE.md`
   - `BACKLOG_PRIORISE.md`
   - `HANDOVER_NOTE.md`
   - `IHU_PRISM_PRESENTATION_FORMAT.md`
3. **source**:
   - `app.py`
   - `tools/`
   - `sample_data/`
4. **artefacts**:
   - `build/`, `dist/`, `results/` clairement marques comme derives.

## 10) Elements de gouvernance projet

- Responsable produit (a confirmer dans le repo cible IHU Prism).
- Responsable technique (reprise codebase + roadmap).
- Process:
  - priorisation mensuelle backlog,
  - release tagging semestriel,
  - revue qualite donnees et securite.

## 11) Kit de transfert Git (pret)

Commandes type (des que l'URL IHU Prism est connue):

```bash
git remote add ihu-prism <URL_DU_REPO_IHU_PRISM>
git push ihu-prism main
```

Si le repo cible est vide et doit devenir source principale:
- verifier default branch,
- proteger `main`,
- appliquer roles (project manager/maintainer) dans les settings GitHub/GitLab.

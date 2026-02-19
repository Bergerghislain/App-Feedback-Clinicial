# App-Feedback-Clinicial

Application desktop (interface graphique) pour permettre a des cliniciens d'evaluer la pertinence de conclusions IA par rapport aux conclusions RCP, a partir de fichiers JSON.

## Objectif

L'application permet de:

- charger 3 JSON (patient, conclusion RCP, conclusion IA) via des chemins locaux;
- charger automatiquement un batch de patients depuis un dossier;
- afficher les informations patient + les 2 conclusions en texte lisible;
- faire remplir un questionnaire de notation de 1 a 5;
- sauvegarder les reponses dans un CSV (une ligne par evaluation/patient);
- enchainer les evaluations sans recharger manuellement les fichiers a chaque patient.

## Structure du projet

- `app.py`: application principale (Tkinter).
- `questions.json`: liste des questions modifiables sans changer le code.
- `sample_data/`: exemples JSON pour tester le flux complet.
- `results/`: dossier par defaut des CSV de sortie.

## Prerequis

- Python 3.9+ (Tkinter inclus par defaut sur la plupart des installations Windows).

## Lancer l'application

Depuis le dossier du projet:

```powershell
python app.py
```

## Utilisation

### Mode manuel (1 patient)

1. Selectionner:
   - le JSON patient;
   - le JSON conclusion RCP;
   - le JSON conclusion IA.
2. Cliquer sur `Charger les donnees`.
3. Lire les informations affichees.
4. Noter toutes les questions (1 a 5), ajouter un commentaire si besoin.
5. Choisir un fichier CSV de sortie puis cliquer `Enregistrer cette evaluation`.

### Mode batch (plusieurs patients)

1. Choisir le `Dossier batch`.
2. Cliquer sur `Charger le batch`.
3. L'application detecte automatiquement les trios JSON (`patient` + `RCP` + `IA`).
4. Remplir le questionnaire puis cliquer `Enregistrer cette evaluation`.
5. L'application charge automatiquement le patient suivant.
6. Utiliser `Patient precedent` / `Patient suivant` si besoin.

Le statut de progression du batch est affiche dans l'interface.

Le CSV contiendra:

- un timestamp;
- l'identifiant patient;
- une cle de batch (`batch_key`);
- les chemins des JSON utilises;
- les scores de chaque question;
- le commentaire libre.

## Convention de nommage pour le batch

Le mode batch fonctionne si le dossier contient des fichiers nommes avec des mots-cles reconnaissables:

- patient: `patient_001.json`, `patient_PAT-001.json`
- RCP: `rcp_eval_001.json`, `rcp_conclusion_PAT-001.json`
- IA: `ia_eval_001.json`, `ai_conclusion_PAT-001.json`

L'appariement se fait automatiquement via:

- l'ID patient trouve dans le JSON (si present), et/ou
- la partie commune du nom de fichier (ex: `001`, `PAT-001`).

Chaque patient doit avoir les 3 JSON requis pour etre charge dans le batch.

## Modifier les questions

Editer `questions.json`:

```json
{
  "questions": [
    { "id": "q1", "text": "Texte de la question 1" },
    { "id": "q2", "text": "Texte de la question 2" }
  ]
}
```

Tu peux ajouter/supprimer des questions. L'interface les recharge au demarrage.

## Exemples JSON fournis

- `sample_data/patient_001.json`
- `sample_data/rcp_eval_001.json`
- `sample_data/ia_eval_001.json`
- `sample_data/patient_002.json`
- `sample_data/rcp_eval_002.json`
- `sample_data/ia_eval_002.json`

Ces fichiers permettent de tester:

- le flux unitaire (mode manuel);
- le flux multi-patients (mode batch) avec enchainement automatique.

## Generer un executable Windows (.exe)

Installer PyInstaller:

```powershell
pip install pyinstaller
```

Construire l'executable:

```powershell
pyinstaller --noconfirm --onefile --windowed --name ClinicianFeedback app.py
```

Le `.exe` sera genere dans:

- `dist/ClinicianFeedback.exe`

Pour distribuer l'outil aux cliniciens, transmettre:

- l'executable;
- un `questions.json` (si tu veux personnaliser le questionnaire);
- les JSON patient/RCP/IA qu'ils doivent charger.

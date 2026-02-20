# App-Feedback-Clinicial

Application desktop permettant a des cliniciens d'evaluer la pertinence de conclusions IA par rapport aux conclusions RCP, a partir de fichiers JSON.

## Objectif

L'application permet de:

- charger 3 JSON (patient, conclusion RCP, conclusion IA) via des chemins locaux;
- charger automatiquement un batch de patients depuis un dossier;
- afficher les informations patient + les 2 conclusions en texte lisible;
- faire remplir un questionnaire de notation de 1 a 5;
- sauvegarder les reponses dans un CSV (une ligne par evaluation/patient);
- enchainer les evaluations sans recharger manuellement les fichiers a chaque patient.

## Structure du projet

- `app.py`: application principale (PyQt6).
- `questions.json`: liste des questions modifiables sans changer le code.
- `sample_data/`: exemples JSON pour tester le flux complet.
- `results/`: dossier par defaut des CSV de sortie.

## Prerequis

- Python 3.9+
- Module Qt pour Python:

```powershell
pip install PyQt6
```

## Lancer l'application

Depuis le dossier du projet:

```powershell
python app.py
```

## Utilisation

### Mode batch automatique (plusieurs patients)

1. Choisir le `Dossier batch`.
2. Cliquer sur `Rafraichir liste JSON`.
3. L'application explore tous les sous-dossiers et detecte automatiquement les trios JSON (`patient` + `RCP` + `IA`).
4. Selectionner un patient dans la liste (a gauche).
5. Remplir le questionnaire puis cliquer `Enregistrer evaluation`.
6. L'application charge automatiquement le patient suivant.
7. Utiliser `Patient precedent` / `Patient suivant` si besoin.

Le statut de progression du batch est affiche dans l'interface.

Le CSV contiendra:

- un timestamp;
- l'identifiant patient;
- une cle de batch (`batch_key`);
- les chemins des JSON utilises;
- les scores de chaque question;
- le commentaire libre.

## Repertoires et appariement batch

Tu peux organiser tes fichiers comme tu veux, par exemple:

- `batch/patients/*.json`
- `batch/rcp/*.json`
- `batch/ia/*.json`

L'application lit recursivement tous les JSON du dossier selectionne puis identifie les roles via:

- le nom du fichier / dossier (`patient`, `rcp`, `ia`, etc.);
- le contenu JSON (champs cliniques patient, texte d'evaluation, source/model).

L'appariement se fait automatiquement via:

- l'ID patient trouve dans le JSON (si present), et/ou
- la partie commune du nom de fichier (ex: `001`, `PAT-001`).

Chaque patient doit avoir les 3 JSON requis pour etre charge dans le batch.
Les JSON de configuration des questions (ex: `questions.json`) sont ignores dans le batch.

## Important pour les cliniciens

- Les cliniciens ne choisissent pas les JSON un par un.
- Ils choisissent seulement le dossier de donnees (ou utilisent le dossier par defaut present dans l'arborescence qui leur ai fournit avec l'executable, en cliquant sur l'executable , un chemin vers le dossier des patients est charge dans l'app par defaut), puis l'app liste les patients prets a evaluer.
-  Ils n'ont qu'a evaluer les evaluations des patients via l'interface une a une , puis cliquer sur patient suivant , et a la fin enregistrer les resultats qui seront telecharges automatiquement dans un dossier results ( qui sera cree si non deja existant ) sous formats csv
- L'export CSV reste automatique: une ligne par patient evalue.

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

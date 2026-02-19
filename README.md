# Plateforme d'évaluation clinique (IA vs RCP)

Application desktop permettant à des cliniciens de :

1. Charger des données patient depuis un JSON.
2. Charger une conclusion RCP (JSON).
3. Charger une conclusion IA (JSON).
4. Visualiser ces informations sous forme de texte simple.
5. Répondre à un questionnaire de notation (1 à 5).
6. Exporter les réponses dans un fichier CSV.

---

## Fonctionnalités principales

- Interface graphique locale (Python + Tkinter).
- Sélection des fichiers par chemin ou via bouton "Parcourir".
- Support de formats JSON flexibles (liste ou dictionnaire).
- Questionnaire personnalisable via un JSON de questions.
- Export CSV avec :
  - patient,
  - question,
  - score,
  - commentaire global,
  - texte RCP et IA.

---

## Structure du projet

- `app.py` : application principale.
- `sample_data/` : exemples prêts à l'emploi.
  - `patients.json`
  - `rcp_evaluations.json`
  - `ai_evaluations.json`
  - `questions.json`

---

## Lancer l'application

Depuis la racine du dépôt :

```bash
python3 app.py
```

Ou en pré-remplissant les chemins :

```bash
python3 app.py \
  --patients sample_data/patients.json \
  --rcp sample_data/rcp_evaluations.json \
  --ia sample_data/ai_evaluations.json \
  --questions sample_data/questions.json \
  --output sample_data/resultats_questionnaire.csv
```

---

## Générer un exécutable

Vous pouvez distribuer l'application sous forme d'exécutable avec PyInstaller :

```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name plateforme-evaluation-clinique app.py
```

L'exécutable sera généré dans le dossier `dist/`.

---

## Format JSON attendu (référence)

### Patients (`patients.json`)

```json
{
  "patients": [
    {
      "patient_id": "P001",
      "nom": "Mme A.",
      "description": "Résumé clinique..."
    }
  ]
}
```

### Évaluations RCP (`rcp_evaluations.json`)

```json
{
  "evaluations": [
    {
      "patient_id": "P001",
      "conclusion": "Conclusion RCP..."
    }
  ]
}
```

### Évaluations IA (`ai_evaluations.json`)

```json
{
  "P001": {
    "conclusion": "Conclusion IA..."
  }
}
```

### Questions (`questions.json`, optionnel)

```json
{
  "questions": [
    {
      "id": "Q1",
      "text": "La recommandation IA est-elle pertinente ?"
    }
  ]
}
```

Si le fichier de questions n'est pas fourni, l'application utilise un questionnaire par défaut.

---

## Sortie CSV

Un enregistrement est ajouté pour chaque question répondue, avec les colonnes :

- `timestamp`
- `clinicien`
- `patient_id`
- `patient_nom`
- `question_id`
- `question_texte`
- `score`
- `commentaire_global`
- `conclusion_rcp`
- `conclusion_ia`

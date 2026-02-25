# App-Feedback-Clinicial

Application desktop PyQt6 pour evaluation clinique en 2 etapes:

- etape 1: evaluation de deux conclusions affichees de facon neutre (`Conclusion 1` et `Conclusion 2`);
- etape 2: evaluation de la reflexion IA pour le meme patient.

L'application collecte automatiquement les resultats dans des CSV dans `results/`.

## Structure attendue

Pour un test clinique, placer les fichiers avec cette structure:

- `app.py`
- `data/` (ou `sample_data/` en fallback)
- `results/` (cree automatiquement si absent)

Le dossier `data/` doit contenir les JSON patients + JSON evaluations (RCP et IA), apparies par patient.

## Test chez un clinicien (acces repo Git)

### 1) Recuperer le repo

```powershell
git clone <URL_DU_REPO>
cd App-Feedback-Clinicial
```

### 2) Installer l'environnement

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3) Lancer l'application

```powershell
python app.py
```

### 4) Parcours utilisateur clinique

1. Ouvrir l'application (les donnees sont chargees depuis `data/` ou `sample_data/`).
2. Lire la description patient (bloc principal, en haut).
3. Noter `Conclusion 1` et `Conclusion 2` (sans connaitre la source IA/RCP).
4. Cliquer `Go to the next page` (les notes de conclusions sont sauvegardees et verrouillees).
5. Sur la page 2, evaluer la reflexion IA (QCM + commentaire).
6. Cliquer `Go to the next patient`.
7. Sur le dernier patient, cliquer `Finish`.

## Fichiers de sortie (collecte resultats)

Apres les evaluations, 3 CSV sont produits dans `results/`:

- `evaluations_conclusion_ia.csv`
- `evaluations_conclusion_rcp.csv`
- `evaluations_reflexion_ia.csv`

Chaque ligne est identifiable de facon unique par:

- `evaluation_id`
- `patient_id`
- `batch_key`
- `timestamp`

## Contenu de demo

Le repo contient des exemples prets a presenter:

- `sample_data/patient_001.json` ... `sample_data/patient_011.json`
- `sample_data/rcp_eval_001.json` ... `sample_data/rcp_eval_009.json`
- `sample_data/ia_eval_001.json` ... `sample_data/ia_eval_009.json`
- `sample_data/ia_reasoning_001.json` ... `sample_data/ia_reasoning_011.json`

## Notes importantes

- Les cliniciens n'importent pas les JSON manuellement depuis l'interface.
- L'etape 1 est volontairement "blindee" (pas de label IA/RCP).
- Une fois l'etape 1 enregistree pour un patient, elle n'est plus modifiable.
- Le bouton `Previous page` permet de revenir consulter la page 1 du meme patient uniquement.

## Build executable (optionnel)

```powershell
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name ClinicianFeedback app.py
```

Executable genere dans `dist/ClinicianFeedback.exe`.

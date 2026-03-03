# App-Feedback-Clinicial

Application desktop PyQt6 pour evaluation clinique en 2 etapes:

- etape 1: evaluation de deux conclusions affichees de facon neutre (`Conclusion 1` et `Conclusion 2`);
- etape 2: evaluation de la reflexion IA pour le meme patient.

L'application collecte automatiquement les resultats dans des CSV dans `results/`.

## Structure attendue

Pour un test clinique, placer les fichiers avec cette structure:

- `app.py`
- `data.zip` (archive chiffree avec code d'acces)
- `.data_access.key` ou `data_access.key` (fichier de cle app pour ouverture automatique)
- `results/` (cree automatiquement si absent)

L'application n'affiche pas de saisie de code au clinicien: elle lit automatiquement la cle app (`.data_access.key` ou `data_access.key`), decompresse `data.zip` temporairement, puis charge les JSON patients + JSON evaluations.
Le `data.zip` distribue est un coffre chiffre avec un `payload.bin` unique (les noms de JSON ne sont pas visibles en clair).

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

1. Ouvrir l'application (aucun code a saisir).
2. Lire la description patient (bloc principal, en haut).
3. Noter `Conclusion 1` et `Conclusion 2` (sans connaitre la source IA/RCP).
4. Cliquer `Go to the next page` (les notes de conclusions sont sauvegardees et verrouillees).
5. Sur la page 2, evaluer la reflexion IA (QCM + commentaire).
6. Cliquer `Go to the next patient`.
7. Sur le dernier patient, cliquer `Finish`.
8. En cas d'interruption, cliquer `Sauvegarder en cours` pour reprendre plus tard.

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
- `sample_data/rcp_eval_001.json` ... `sample_data/rcp_eval_011.json`
- `sample_data/ia_eval_001.json` ... `sample_data/ia_eval_011.json`
- `sample_data/ia_reasoning_001.json` ... `sample_data/ia_reasoning_011.json`

## Notes importantes

- Les cliniciens n'importent pas les JSON manuellement depuis l'interface.
- L'etape 1 est volontairement "blindee" (pas de label IA/RCP).
- Une fois l'etape 1 enregistree pour un patient, elle n'est plus modifiable.
- Le bouton `Previous page` permet de revenir consulter la page 1 du meme patient uniquement.
- Les donnees de `data.zip` sont extraites dans un dossier temporaire puis nettoyees a la fermeture de l'application.
- Si `data.zip` est present, un fichier de cle (`.data_access.key` ou `data_access.key`) doit etre present pour un lancement sans interaction.
- La progression est reprise automatiquement a partir des CSV, et un brouillon de session est conserve dans `results/progress_draft.json`.

## Gestion du zip securise (developpeur)

Pour preparer ou modifier le contenu de `data.zip` avec mot de passe:

```powershell
# Creer/mettre a jour data.zip depuis un dossier data/
# + generer automatiquement .data_access.key pour l'app
python tools/data_zip_manager.py pack --source data --zip data.zip

# Variante: pack puis suppression du dossier data clair
python tools/data_zip_manager.py pack-and-hide --source data --zip data.zip

# Dechiffrer data.zip pour edition (si tu connais le code)
python tools/data_zip_manager.py unpack --zip data.zip --output .

# Option: ne pas generer .data_access.key (usage manuel/dev seulement)
python tools/data_zip_manager.py pack --source data --zip data.zip --no-app-key
```

## Build executable (optionnel)

```powershell
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name ClinicianFeedback app.py
```

Executable genere dans `dist/ClinicialFeedback.exe`.

## Livraison aux cliniciens

Dossier a transmettre tel quel:

- `dist/ClinicialFeedback.exe`
- `dist/data.zip`
- `dist/data_access.key` (ou `.data_access.key`)
- `dist/results/` (dossier vide au depart)

Mode d'utilisation clinique:

1. Le clinicien ouvre `ClinicialFeedback.exe`.
2. L'app charge automatiquement les patients depuis `data.zip`.
3. Les CSV de collecte sont ecrits dans `dist/results/`.

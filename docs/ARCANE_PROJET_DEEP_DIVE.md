# Arcane - Dossier technique detaille (etat actuel)

## 1) Resume executif

Le projet **Arcane** (nom de travail) est aujourd'hui une **application desktop PyQt6** pour evaluation clinique en deux etapes:

1. Evaluation comparee de deux conclusions (affichage blinde `Conclusion A/B`).
2. Evaluation de la reflexion IA associee au meme patient.

Il n'y a **pas** de stack web separee (pas d'API backend, pas de frontend navigateur). Le "frontend" et la logique "backend local" cohabitent dans `app.py`.

---

## 2) Architecture actuelle (front/back dans une app locale)

### Frontend (local UI)
- Framework: **PyQt6**
- Composants:
  - `QMainWindow` principal.
  - `QStackedWidget` pour les 2 etapes.
  - `QPlainTextEdit` pour affichage patient/conclusions/reflexion.
  - Boutons notables: `Aller a l'etape 2`, `Patient suivant`, `Sauvegarder en cours`.
- UX:
  - Progression patient visible.
  - Etape 1 verrouillee apres sauvegarde.
  - Brouillon local reprenable.

### Backend (local processing)
- Chargement auto des donnees depuis `data.zip` (AES via `pyzipper`) + cle applicative.
- Detection automatique des triplets patient/RCP/IA via heuristiques de nommage + contenu JSON.
- Export resultats CSV (3 fichiers metiers).
- Reprise d'avancement depuis CSV + brouillon JSON.

### Securite des donnees (etat actuel)
- `data.zip` chiffre (AES) contenant un unique `payload.bin` (les noms de JSON ne sont pas exposes en clair dans l'enveloppe externe).
- Cle applicative obfusquee (`.data_access.key`) pour lancement sans saisie.
- Nettoyage du dossier temporaire extrait a la fermeture.

---

## 3) Inventaire des fichiers et role de chacun

> Inventaire fonctionnel du contenu versionne (hors metadonnees Git).

## 3.1 Racine

1. `app.py`  
   - Fichier coeur de l'application (UI + logique metier locale + persistence CSV).
2. `README.md`  
   - Guide usage, packaging, securite, livraison clinicien.
3. `requirements.txt`  
   - Dependances Python (`PyQt6`, `pyzipper`).
4. `questions.json`  
   - Questions de notation de l'etape 1 (personnalisables).
5. `ClinicialFeedback.spec`  
   - Configuration PyInstaller pour generer l'executable Windows.
6. `data_access.key`  
   - Token obfusque contenant le mot de passe `data.zip` (fichier sensible).

## 3.2 Outils

7. `tools/data_zip_manager.py`  
   - Utilitaire admin pour:
     - construire `data.zip` chiffre (`pack`, `pack-and-hide`),
     - dechiffrer (`unpack`),
     - regnerer une cle app perdue (`recover-key`),
     - inspecter/valider une cle (`inspect-key`).

## 3.3 Donnees de demo

8-18. `sample_data/patient_001.json` ... `sample_data/patient_011.json`  
   - Descriptions patient (id, age, contexte, diagnostic, traitements, etc.).
19-29. `sample_data/rcp_eval_001.json` ... `sample_data/rcp_eval_011.json`  
   - Conclusions RCP.
30-40. `sample_data/ia_eval_001.json` ... `sample_data/ia_eval_011.json`  
   - Conclusions IA (et parfois champs de raisonnement).
41-51. `sample_data/ia_reasoning_001.json` ... `sample_data/ia_reasoning_011.json`  
   - Raisonnements IA detailles (texte + etapes).

## 3.4 Resultats runtime

52. `results/evaluations_conclusion_ia.csv`  
   - Notes des conclusions dont source reelle IA.
53. `results/evaluations_conclusion_rcp.csv`  
   - Notes des conclusions dont source reelle RCP.
54. `results/evaluations_reflexion_ia.csv`  
   - QCM + commentaire de reflexion IA.
55. `results/progress_draft.json`  
   - Brouillon de progression local (reprise de session).

## 3.5 Package de distribution / livraison

56. `dist/.data_access.key`  
57. `dist/data_access.key`  
58. `dist/results/evaluations_conclusion_ia.csv`  
59. `dist/results/evaluations_conclusion_rcp.csv`  
60. `dist/results/evaluations_reflexion_ia.csv`  
   - Snapshot distribution / execution locale.

## 3.6 Release cliniciens

61. `release_cliniciens/data_access.key`  
62. `release_cliniciens/questions.json`  
63. `release_cliniciens/results/progress_draft.json`  
   - Variante de livraison cible utilisateur.

## 3.7 Artefacts de build PyInstaller

64. `build/ClinicialFeedback/Analysis-00.toc`  
65. `build/ClinicialFeedback/EXE-00.toc`  
66. `build/ClinicialFeedback/PKG-00.toc`  
67. `build/ClinicialFeedback/PYZ-00.toc`  
68. `build/ClinicialFeedback/warn-ClinicialFeedback.txt`  
69. `build/ClinicialFeedback/xref-ClinicialFeedback.html`  
   - Fichiers generes automatiquement pendant le packaging.

## 3.8 Resultats agreges

70. `results/evaluations_conclusion_ia.csv` (metier courant)  
71. `results/evaluations_conclusion_rcp.csv` (metier courant)  
72. `results/evaluations_reflexion_ia.csv` (metier courant)  
73. `results/progress_draft.json` (metier courant)  
   - Utilises pour reprise/collecte (deja listés ci-dessus, gardes ici pour clarte metier).

---

## 4) Details fonction par fonction

## 4.1 Fonctions globales (`app.py`)

- `get_app_base_dir()`  
  Determine le dossier base (mode script vs executable fige).
- `get_first_present_value(source, keys)`  
  Renvoie la premiere valeur non vide parmi plusieurs alias de cle.
- `format_value(value)`  
  Normalise l'affichage texte (list/dict/scalar).
- `normalize_pair_key(raw_value)`  
  Normalise les identifiants pour faire des correspondances robustes.
- `tokenize_name(value)`  
  Tokenisation alpha-numerique des noms de fichiers.
- `derive_key_from_filename(path)`  
  Derive une cle de pairing depuis un nom de fichier.
- `infer_role_from_path(path)`  
  Heuristique de role (`patient`, `rcp`, `ia`) via nom de fichier/dossier.
- `infer_role_from_payload(payload)`  
  Heuristique de role via structure et contenu JSON.
- `extract_patient_id_from_payload(payload)`  
  Extrait `patient_id`/`id` y compris structure imbriquee.
- `normalize_patient_payload(payload)`  
  Aplati les enveloppes JSON vers l'objet patient utile.
- `normalize_evaluation_payload(payload)`  
  Aplati les enveloppes JSON vers l'objet evaluation utile.
- `format_patient_description(patient_data)`  
  Transforme les champs patient en texte lisible pour clinicien.
- `extract_evaluation_text(data)`  
  Recupere le texte principal d'une conclusion.
- `load_questions_from_json(path)`  
  Charge les questions externes, fallback vers `DEFAULT_QUESTIONS`.
- `detect_csv_delimiter(path)`  
  Detecte `;` vs `,` sur un CSV existant.
- `read_csv_rows(path)`  
  Lecture robuste d'un CSV en liste de dictionnaires.
- `bootstrap_collection_csv(default_path)`  
  Fusion legacy CSV vers `evaluations.csv` (migration legacy).
- `get_collection_csv_path()`  
  Retourne le chemin CSV de collecte agregee.
- `_xor_bytes(data, key)`  
  Primitive d'obfuscation simple.
- `decode_app_data_password(token)`  
  Decode une cle app obfusquee en mot de passe clair.
- `blind_question_text(text)`  
  Neutralise la terminologie IA/RCP dans les labels de question.
- `discover_patient_bundles(root)`  
  Detecte, assemble et trie les triplets patient + RCP + IA.
- `main()`  
  Point d'entree Qt.

## 4.2 Classe `PatientBundle`

Structure de donnees representant un triplet:
- chemins JSON (`patient_path`, `rcp_path`, `ia_path`),
- payloads charges (`patient_data`, `rcp_data`, `ia_data`),
- identifiants (`key`, `patient_id`).

## 4.3 Classe `ClinicianFeedbackApp` (methodes)

### Initialisation / setup
- `__init__` : initialise etat app, charge progression, construit UI.
- `_default_data_dir` : fallback `data/` puis `sample_data/`.
- `_candidate_base_dirs` : liste ordonnee de repertoires candidats.
- `_resolve_data_dir` : resolution auto de source donnees (`data.zip` ou dossier).
- `_load_data_zip_password` : lit mot de passe depuis env ou fichier cle.
- `_extract_data_zip_silent` : extraction temporaire securisee de `data.zip`.
- `_extract_nested_payload_if_present` : decompresse `payload.bin` interne.
- `_extract_zip_content` : extraction zip AES (pyzipper) avec fallback.
- `_locate_data_directory` : detecte le dossier contenant les JSON.

### Construction UI
- `_build_ui` : cree l'ensemble des widgets, pages et bindings.
- `_wrap_in_scroll_area` : encapsule une page dans une zone scrollable.
- `_apply_styles` : stylesheet Qt complet.
- `_on_step_changed` / `_set_active_step` : gestion badges etape active.

### Etats d'interface / progression
- `_update_comment_counter` : compteur live du commentaire libre.
- `_set_status` : met a jour la barre de statut fonctionnelle.
- `_find_bundle_key` : mappe id patient / batch vers cle de bundle.
- `_read_csv_rows` : lecture CSV interne orientee progression.
- `_load_existing_progress` : reconstruit etat a partir des CSV existants.
- `_save_progress_draft` : snapshot brouillon local JSON.
- `_restore_draft_progress_if_any` : prepare reprise depuis brouillon.
- `_apply_pending_draft_if_needed` : reapplique les choix brouillon dans l'UI.

### Chargement patient / evaluation
- `_extract_reasoning_text` : extrait la reflexion IA.
- `_assign_conclusion_mapping` : randomisation deterministe A/B vs IA/RCP.
- `_set_page1_editable` : active/desactive edition etape 1.
- `_reset_page1_form` / `_reset_page2_form` : reset formulaires.
- `_update_header` : progression globale.
- `_load_current_patient` : hydrate l'UI avec le patient courant.

### Validation et persistence des reponses
- `_collect_page1_scores` : verifie complétude et recupere notes 1..5.
- `_collect_page2_answers` : verifie complétude du QCM reflexion IA.
- `_on_page1_next` : enregistre etape 1 (CSV IA + CSV RCP) puis verrouille.
- `_on_page2_previous` : navigation retour.
- `_on_page2_next_patient` : enregistre etape 2, incremente progression, passe au patient suivant.
- `append_row_to_csv` : ecriture CSV robuste avec fusion de colonnes dynamiques.
- `closeEvent` : sauvegarde brouillon + nettoyage des donnees temporaires.

## 4.4 Fonctions (`tools/data_zip_manager.py`)

- `_xor_bytes` / `encode_app_data_password` / `decode_app_data_password`  
  Encodage/decodage de la cle applicative.
- `write_app_key_file`  
  Ecrit `.data_access.key`.
- `build_inner_zip_bytes`  
  Construit un zip interne `data/...` en memoire.
- `pack_data_folder`  
  Cree `data.zip` AES + cle app.
- `validate_zip_password`  
  Verifie qu'un mot de passe ouvre effectivement l'archive.
- `recover_app_key`  
  Flux "mot de passe oublie": regenere la cle app perdue.
- `inspect_app_key`  
  Inspecte une cle et optionnellement la valide contre une archive.
- `unpack_data_zip`  
  Dechiffre et extrait `data.zip`.
- `remove_plain_data_folder`  
  Supprime la source claire post-pack (`pack-and-hide`).
- `main`  
  CLI d'orchestration.

---

## 5) Choix d'implementation: avantages / inconvenients

## 5.1 Monolithe `app.py`

**Avantages**
- Delivery rapide.
- Peu de friction de deploiement.
- Lisibilite immediate pour petite equipe.

**Inconvenients**
- Couplage UI + metier + persistence.
- Testabilite limitee (quasi pas de couches isolables).
- Evolutivite reduite (ajouts complexes plus couteux).

## 5.2 CSV comme stockage

**Avantages**
- Portable, inspectable facilement.
- Integrable simplement dans Excel/SPSS/R.

**Inconvenients**
- Concurrence d'ecriture non geree.
- Evolution schema fragile (colonnes dynamiques).
- Validation de donnees faible vs base relationnelle.

## 5.3 Heuristiques de discovery JSON

**Avantages**
- Tolerance a des formats heterogenes.
- Moins de contraintes sur producteurs de JSON.

**Inconvenients**
- Risque de faux positifs si nommage ambigu.
- Debug plus difficile qu'une convention stricte versionnee.

## 5.4 Securisation `data.zip` + cle obfusquee

**Avantages**
- UX clinique simple (sans saisie).
- Obfuscation minimale protege contre exposition triviale.
- Chiffrement AES de l'archive.

**Inconvenients**
- La cle obfusquee reste recuperable (ce n'est pas un coffre fort HSM).
- Si cle et archive sont co-distribuees, securite repose surtout sur l'environnement.
- Pas de rotation/expiry automatisee.

---

## 6) Axes d'amelioration (ordre technique)

## P0 (fiabilite immediate)
1. Ajouter tests unitaires sur parsing/discovery/export.
2. Introduire validation de schema JSON (Pydantic/JSON schema).
3. Ajouter `.gitignore` et politique de secret handling stricte.

## P1 (maintenabilite)
1. Refactor en modules:
   - `ui/`,
   - `domain/`,
   - `io/`.
2. Introduire service d'export (CSV writer dedie + verrouillage fichier).
3. Instrumentation logs structuree (niveau INFO/WARN/ERROR).

## P2 (produit)
1. Ecran diagnostics "integrite data.zip / cle".
2. Localisation FR/EN.
3. Tableau recapitulatif pre-export.

## P3 (industrialisation)
1. CI lint/tests/build executable.
2. Signature binaire de release.
3. Versioning semantique + changelog formalise.

---

## 7) "Frontend / Backend" - formulation exacte a donner a un ingenieur

Tu peux repondre ainsi:

> "Le projet n'est pas un produit web separe en frontend React + backend API. C'est une application desktop PyQt6 monolithique: la couche de presentation (widgets Qt), la logique metier (construction des bundles patient/RCP/IA, neutralisation A/B, validation des formulaires) et la persistence (CSV + brouillon JSON + extraction temporaire de donnees chiffrees) sont implantees ensemble dans `app.py`."

---

## 8) Verification de l'etat actuel

- Application orientee usage terrain clinicien, operationnelle en local.
- Flux principal de collecte en 2 etapes implementé.
- Reprise de progression implementee.
- Flux "mot de passe oublie" (perte de cle app) complete via `recover-key`.
- Documentation de passation et backlog priorise ajoutes (voir dossier `docs/`).

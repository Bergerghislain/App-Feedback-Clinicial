# Checklist de transfert vers le Git IHU Prism

> Objectif: transfert integral du projet et alignement de presentation.

## 1) Pre-requis

- URL du depot cible IHU Prism.
- Droits `maintain`/`admin` sur ce depot cible.
- Identifiant GitHub/GitLab exact de **Hakim**.

## 2) Gouvernance repository

1. Ajouter Hakim avec un role de pilotage (`maintain` ou `admin` selon politique org).
2. Definir protections de branche (`main` protegee).
3. Verifier les permissions d'ecriture de l'equipe produit/technique.

## 3) Push du code

```bash
git remote add ihu-prism <URL_DU_REPO_IHU_PRISM>
git push ihu-prism main
```

## 4) Alignement format IHU Prism (dans le repo)

- `README.md` a jour.
- `docs/IHU_PRISM_PRESENTATION_FORMAT.md` present.
- `docs/ARCANE_PROJET_DEEP_DIVE.md` present.
- `docs/BACKLOG_PRIORISE.md` present.
- `docs/HANDOVER_NOTE.md` present.

## 5) Verification post-transfert

1. Cloner le nouveau repo cible.
2. Lancer:
   - `pip install -r requirements.txt`
   - `python app.py`
3. Verifier creation CSV dans `results/`.
4. Verifier flux `recover-key`:
   - `python tools/data_zip_manager.py recover-key --zip data.zip --app-key-file .data_access.key`

## 6) Notes importantes

- Sans URL cible et sans droits d'administration org, l'affectation de role (Project Manager) ne peut pas etre automatisee depuis ce depot.
- Cette checklist sert de procedure d'execution immediate des que les acces sont disponibles.

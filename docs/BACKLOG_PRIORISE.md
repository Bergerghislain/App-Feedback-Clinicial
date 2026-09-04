# Backlog priorise - Arcane (etat actuel)

## Regles de priorisation

- **P0 (Critique):** securite, integrite des donnees, risque de blocage clinique.
- **P1 (Haute):** fiabilite et maintenabilite majeures.
- **P2 (Moyenne):** productivite, ergonomie, diffusion.
- **P3 (Basse):** confort, optimisation non bloquante.

---

## P0 - A traiter en premier

### ARC-001 - Politique de secrets et hygiene repo
- **Probleme:** fichiers de cle (`data_access.key`) et artefacts runtime peuvent etre versionnes.
- **Action:** ajouter `.gitignore`, nettoyer historique si necessaire, formaliser politique de distribution des cles.
- **Impact:** reduit le risque de fuite d'acces data.

### ARC-002 - Tests minimaux sur logique coeur
- **Probleme:** pas de test automatise.
- **Action:** tests unitaires sur `discover_patient_bundles`, parsing JSON, export CSV, `decode_app_data_password`.
- **Impact:** diminue regressions silencieuses.

### ARC-003 - Validation schema des JSON cliniques
- **Probleme:** heuristiques permissives peuvent accepter des donnees incorrectes.
- **Action:** imposer schema minimal (champs obligatoires, types attendus), log d'anomalies.
- **Impact:** meilleure qualite et traçabilité des evaluations.

---

## P1 - Haute priorite

### ARC-010 - Refactor modulaire de `app.py`
- **Probleme:** couplage UI/metier/persistence fort.
- **Action:** separer en modules `ui/`, `domain/`, `storage/`, `security/`.
- **Impact:** code plus evolutif et testable.

### ARC-011 - Journalisation structuree
- **Probleme:** erreurs et diagnostics majoritairement via popups.
- **Action:** ajouter logging fichier (niveau info/warn/error + contexte patient_id).
- **Impact:** debug plus rapide en production terrain.

### ARC-012 - Controle de concurrence ecriture CSV
- **Probleme:** ecritures concurrentes possibles si multi-instance.
- **Action:** file lock local + warning si fichier verrouille.
- **Impact:** evite corruption partielle des exports.

---

## P2 - Priorite moyenne

### ARC-020 - Ecran de diagnostic securite
- **Action:** UI pour verifier presence/validite de `data.zip` et `.data_access.key`.

### ARC-021 - Resume avant validation finale
- **Action:** page recapitulatif des reponses avant enregistrement etape 2.

### ARC-022 - Internationalisation FR/EN
- **Action:** extraction des labels, fichier de traduction.

### ARC-023 - Nomenclature package/repo
- **Action:** harmoniser `Clinicial` -> `Clinical`, nettoyer noms historiques.

---

## P3 - Faible priorite

### ARC-030 - Theme UI adaptatif
- **Action:** mode contraste eleve / accessibilite.

### ARC-031 - Export additionnel JSONL/Parquet
- **Action:** formats analytics avancees.

### ARC-032 - Dashboard local de statistiques
- **Action:** visualisations descriptives des scores collectes.

---

## Ordre d'execution recommande

1. ARC-001
2. ARC-002
3. ARC-003
4. ARC-010
5. ARC-011
6. ARC-012
7. ARC-023
8. ARC-020
9. ARC-021
10. ARC-022
11. ARC-030
12. ARC-031
13. ARC-032

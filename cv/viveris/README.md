# CVs Viveris — format Canva (HTML → PDF)

| Priorité | Offre | PDF |
|---|---|---|
| 1 | Ingénieur Validation & Vérification Logiciel Embarqué (Lyon) | `Ghislain_THEUBO_Viveris_Validation_Verification.pdf` |
| 2 | Ingénieur Logiciel Embarqué — Ferroviaire (Lyon) | `Ghislain_THEUBO_Viveris_Embarque_Ferroviaire.pdf` |
| 3* | Développeur Java MCO (Grenoble) — candidature ambitieuse | `Ghislain_THEUBO_Viveris_Java_MCO_Grenoble.pdf` |

Sources HTML éditables dans ce dossier. Régénération PDF :

```bash
google-chrome --headless --no-sandbox --disable-gpu --no-pdf-header-footer \
  --print-to-pdf=out.pdf file://$PWD/cv1_validation_verification.html
```

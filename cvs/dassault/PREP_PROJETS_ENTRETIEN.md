# Plan projets perso avant entretien (Dassault)

Objectif : que chaque projet cité sur le CV existe vraiment sur GitHub, avec README, tests, et une démo de 3–5 minutes.

## Priorité 1 — Offre Ingénieur IA (550014)

**Repo :** `plm-lifecycle-langgraph-agent`

| Jour | Livrable |
|------|----------|
| 1–2 | Graphe LangGraph (nodes plan / retrieve / act / summarize) sur un mock PLM JSON |
| 3 | API FastAPI + schémas Pydantic + traces |
| 4 | RAG minimal sur 10–20 docs techniques + 5 questions d’éval |
| 5 | README + diagramme + script démo |

**Parler en entretien :** communalisation d’infra agents, robustesse, specs, tests, limites des LLM.

## Priorité 2 — Offre Java / Web / Rust (550043)

**Repo :** `mini-lsp-systems-dsl`

| Jour | Livrable |
|------|----------|
| 1–2 | Grammaire ANTLR + AST + table de symboles |
| 3 | LSP4J : completion, hover, diagnostics |
| 4 | Workspace multi-fichiers + index + invalidation |
| 5 | (Bonus) petit binaire Rust pour search/index hot-path |

**Parler en entretien :** incremental analysis, caching, APIs basse latence, IDE tooling (clangd / rust-analyzer comme références).

## Priorité 3 — Offre Interopérabilité (550893)

**Repo :** `eng-data-converter-cpp`

| Jour | Livrable |
|------|----------|
| 1–2 | Parsers JSON/XML/CSV + mapping de schémas versionnés |
| 3 | Gestion d’erreurs + tests Catch2 sur cas malformés |
| 4 | Pipeline batch multithread + micro-benchmarks |
| 5 | Petite UI JS qui appelle le CLI |

**Parler en entretien :** volumétrie, compatibilité, specs robustes, perf, collaboration internationale.

## Règles d’honnêteté en entretien

- Dire clairement : « projet personnel réalisé pour monter en compétence sur X ».
- Ne pas prétendre que c’était en prod chez un employeur.
- Avoir 1 métrique réelle (temps de parse, latence p95, recall@k, couverture tests).

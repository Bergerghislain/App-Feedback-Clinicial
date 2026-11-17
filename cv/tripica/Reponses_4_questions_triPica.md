# Réponses candidature triPica — Java Fullstack

Ton : humain, direct, collectif (ils filtrant la “gloire perso”).  
Objectif : passer le filtre Sami → lead tech (algo) → direction.

---

## 1. Pourquoi aimez-vous ce métier ?

Ce qui me plaît, c’est de transformer un besoin un peu flou en quelque chose qui marche vraiment pour les gens qui l’utilisent.

J’aime le côté “artisanat + équipe” : comprendre le problème, proposer une solution simple, écrire du code propre, le tester, le faire revuer, le déployer, puis corriger quand la réalité terrain dit autre chose. Le moment où une feature passe en prod et que ça débloque une équipe, c’est ça qui me motive — pas le titre sur LinkedIn.

J’aime aussi les produits complexes (plusieurs services, plusieurs clients, beaucoup d’edge cases). Ça force à être rigoureux sans se prendre au sérieux, et à travailler vraiment en collectif. C’est exactement l’esprit que je lis chez triPica.

---

## 2. Combien d'années d'expérience professionnelle (hors stage, alternance compte comme moitié) avez-vous en Java ?

**Réponse courte (si champ numérique) :** `1`

**Réponse recommandée (si texte libre) :**

Environ **1 an** si on compte la pratique Java sérieuse (projets école Ensimag + montée perso Spring/Hibernate).  
En entreprise, mon expérience backend prod est surtout en **Python/FastAPI** et **C#/.NET** (même réflexes OO, APIs, SQL, tests, CI/CD). Je suis transparent : je ne prétends pas 4 ans de Java en prod. En revanche je code tous les jours, je monte vite, et Java est un choix assumé pour triPica (Spring / Javalin).

> Ne mets pas 3–4 ans : le lead tech le verra sur CondIngame / l’échange code, et ça casse la confiance.

---

## 3. Pourquoi avoir choisi le langage Java ?

Parce que c’est un langage d’écosystème solide pour des produits SaaS qui doivent durer : typage, outillage, Spring, Hibernate, culture industrialisation (tests, CI, revues).

Je l’ai découvert sérieusement à l’école, et ce qui m’a accroché c’est moins “la syntaxe” que le fait de pouvoir construire des services robustes, lisibles par une équipe, maintenables dans le temps. Chez triPica vous êtes pile sur ça (Java à jour, SpringBoot / Javalin, microservices AWS, qualité).

Aujourd’hui je viens surtout du backend Python/C#, donc mon choix Java pour cette candidature est clair : je veux m’ancrer sur votre stack produit, pas collectionner les langages pour le CV. Vous dites que vous faites monter en compétence sur les versions — parfait, j’apprends vite dès que je suis dans le code et les revues d’équipe.

---

## 4. Parlez-moi du projet le plus complexe sur lequel vous avez travaillé.

Le plus complexe, c’est la **plateforme data** que j’ai construite à **Gustave Roussy / CentraleSupélec (labo MICS)** en 2026.

Le truc dur, ce n’était pas “écrire une API” : c’était de faire tenir ensemble plein de contraintes en même temps.

- Données sensibles (recherche / santé) → droits d’accès, validation, traçabilité.
- Besoins métier souvent ambigus → il fallait challenger, cadrer, prioriser avec des non-dev.
- Stack bout-en-bout : **Python/FastAPI + PostgreSQL + React**, auth JWT/RBAC, SQL à optimiser (lectures critiques ~30 % plus rapides après indexation).
- Qualité : tests, Docker, CI, docs, et ownership quand ça cassait.

Le vrai défi, c’était l’**intégration** : plusieurs sources, plusieurs utilisateurs, peu de droit à l’erreur sur la donnée, et une UI que les gens doivent réellement adopter. J’ai appris à découper, livrer petit, mesurer l’usage, et ne pas sur-ingénierer. C’est le genre de complexité “produit multi-projets” que je retrouve dans votre annonce.

---

## 5. Avez-vous déjà développé en utilisant l’IA ? Si oui, parlez-moi d’un de ces projets.

Oui — tous les jours, surtout chez **Shift Technology**, et aussi sur mes side projects.

Exemple concret : sur un ticket de modernisation / bug backend, je m’en sers (Claude / Cursor) pour explorer le code, proposer un plan, générer une première version de fix + tests. Ensuite je fais le travail sérieux : je relis le diff ligne à ligne, je vérifie les edge cases, je lance les tests, et je ne merge que si je comprends et assume le changement. L’IA accélère ; elle ne signe pas à ma place.

Autre usage : à Gustave Roussy, pour accélérer la doc d’API et des cas de test à partir des specs — toujours avec relecture humaine, parce que la doc pourrie coûte plus cher qu’elle ne rapporte.

En gros : je suis très à l’aise avec l’IA comme copilote, et très strict sur la responsabilité du code en prod. Ça colle à une équipe qui livre souvent et qui se revue.

---

## Mini-conseil avant d’envoyer

1. Colle ces réponses telles quelles (ou raccourcis un peu si limite de caractères).
2. Sur Java années : **reste à ~1** (honnête).
3. Après envoi, message LinkedIn court à **Sami Chehab** : motivation + dispo call 30 min.
4. Pour CondIngame : révise algo classique (arrays, maps, complexity) — le lead tech “adore” ça.

### Message Sami (optionnel, même jour)

Bonjour Sami,

Je viens de postuler au poste Java Fullstack via les 4/5 questions.

Ce qui m’attire chez triPica : produit SaaS complexe, collectif, Java tenu à jour, vrai ownership (specs → code → tests → prod). Mon socle est backend/prod (Python/C#) + montée Java/Spring assumée — je préfère être transparent que gonfler les années Java.

Dispo pour les 30 min motivation quand tu veux.

Ghislain THEUBO — 06 82 86 62 79

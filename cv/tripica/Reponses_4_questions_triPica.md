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

*(version développée — à coller telle quelle)*

Le projet le plus complexe sur lequel j’ai travaillé, c’est la **plateforme data** construite à **Gustave Roussy avec le labo MICS de CentraleSupélec** (CDD, 2026).

Sur le papier, ça peut ressembler à “une app FastAPI + React”. En vrai, la complexité venait du fait que **tout devait tenir en même temps**, avec peu de droit à l’erreur.

**Le contexte**  
On avait des données de recherche / santé, donc sensibles : pas question de bricoler. Il fallait contrôler qui voit quoi, valider ce qui entre, et garder une trace crédible de ce qui se passe. En face, les utilisateurs n’étaient pas des dévs : chercheurs, métiers, profils très différents, avec des besoins souvent flous ou contradictoires (“on veut juste pouvoir accéder aux données”… sauf que derrière il y a 10 règles implicites).

**Ce que j’ai vraiment fait**  
J’ai pris le sujet de bout en bout :
- reformuler les besoins en specs et critères d’acceptation compréhensibles ;
- concevoir le modèle **PostgreSQL** et les **APIs Python/FastAPI** (validation, auth **JWT**, **RBAC**) ;
- brancher un front **React/Vite** pour que les gens puissent vraiment explorer et agir, pas juste “consommer un endpoint” ;
- industrialiser un minimum : tests, **Docker**, **CI**, documentation, logs.

Un exemple concret de complexité technique : certaines lectures SQL critiques étaient trop lentes pour l’usage réel. J’ai travaillé indexation / requêtes, et on a gagné de l’ordre de **~30 %** sur ces lectures. Pas un exploit de hero coding — juste du travail propre, mesuré, utile.

**Pourquoi c’était le plus dur**  
Parce que le problème n’était pas un algo isolé. C’était un système :
plusieurs sources / cas d’usage, plusieurs profils utilisateurs, contraintes de qualité de donnée, et une obligation d’**adoption**. Si l’outil est techniquement correct mais personne ne s’en sert, c’est un échec.

J’ai appris à découper, livrer petit, challenger les demandes, et ne pas sur-ingénierer. Exactement le genre de complexité “produit multi-sujets / multi-équipes” que je retrouve dans l’annonce triPica (specs, code, tests, déploiement, coordination).

---

## 5. Avez-vous déjà développé en utilisant l’IA ? Si oui, parlez-moi d’un de ces projets.

*(version développée — à coller telle quelle)*

Oui, et pas juste “j’ai essayé ChatGPT une fois”. Je développe **avec l’IA au quotidien**, surtout chez **Shift Technology**, avec **Claude / Cursor**.

**Un projet / usage concret**  
Sur des tickets backend de prod (bug, modernisation, petit feature), mon process est toujours le même :

1. Je cadre le problème moi-même (repro, impact, contraintes).
2. Je demande à l’IA d’explorer le code, de proposer un plan, parfois un premier draft de fix + tests.
3. Ensuite je fais le vrai travail d’ingénieur : je **relis le diff ligne à ligne**, je chasse les hallucinations, je vérifie les edge cases, je lance les tests, je regarde les régressions.
4. Je ne merge **que** si je comprends et j’assume le changement. L’IA n’a pas de responsabilité en prod — moi si.

Ça m’a clairement fait gagner du temps sur l’exploration et le boilerplate, surtout dans une codebase que je découvre. Mais dès qu’il y a un risque métier / prod, je ralentis et je valide comme un humain.

**Autre exemple (Gustave Roussy)**  
Je m’en suis aussi servi pour accélérer la **doc d’API** et des **cas de test** à partir des specs. Là encore : draft IA → relecture humaine. Une doc fausse fait plus de dégâts qu’une doc absente, donc pas de copier-coller aveugle.

En résumé : je suis très à l’aise avec l’IA comme **copilote**, et très strict sur l’**ownership**. Pour une équipe qui livre souvent, se revue, et veut de la qualité (comme triPica), c’est exactement l’usage que je défends.

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

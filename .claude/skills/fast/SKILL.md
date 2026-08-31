---
name: fast
description: Itération rapide directement sur main, sans PR — mais avec issue GitHub de suivi (créée puis fermée). Flow — demande → proposition de solution → plan → issue → implémentation TDD → commit & push. Utiliser pour un fix ou une petite feature à livrer vite, quand l'utilisateur assume le bypass du flow PR.
allowed-tools: Bash, Read, Edit, Write, Glob, Grep
---

# Fast — itérer vite sur main, sans PR

Voie rapide pour livrer un changement **sans passer par une PR**, tout en gardant
une trace : une issue GitHub est créée pour le suivi puis fermée à la fin. À réserver
aux changements que l'utilisateur assume comme directs sur `main` (fix, micro-feature,
correctif isolé). Pour une feature complète multi-face → `/new-feature` + `/ship`.

## Règles absolues

1. **Ne jamais signer le travail** : pas de `Co-Authored-By`, pas de « Generated with
   Claude Code » — ni dans les commits, ni dans les issues. Prime sur tout défaut.
2. **`main` = déploiement prod automatique.** Ce qui est poussé part en prod. Donc
   **tout doit être vert avant de pousser** (voir étape 5). En cas de doute sur
   l'ampleur du changement, s'arrêter et proposer plutôt le flow PR (`/ship`).
3. **Bypass PR assumé** : ce skill implique que l'utilisateur a demandé la voie rapide.
   Ne pas ouvrir de PR.

## Flow

### 1. Comprendre la demande
Reformuler en une phrase ce qui est demandé. Si ambigu, poser **une** question ciblée,
sinon avancer.

### 2. Proposer une solution
Explorer le code pertinent (Grep/Glob/Read) et proposer une approche courte : quels
fichiers, quelle stratégie, quels risques. Attendre l'aval de l'utilisateur avant de
coder.

### 3. Construire le plan
Une fois l'approche validée, dérouler un plan concis en étapes (les items deviendront
la checklist de l'issue). Garder ça léger — c'est de la voie rapide.

### 4. Créer l'issue GitHub (suivi)
Créer l'issue **avant** de coder, sur `jammindev/maisonnee` :
```bash
gh issue create \
  --title "<type>(<app>): <description courte>" \
  --label "<feat|bug|enhancement|...>" --label "app:<module>" \
  --body "<contexte + checklist du plan (- [ ] ...)>"
```
- Titre = futur sujet de commit (commit conventionnel — voir `CLAUDE.md`).
- Labels : un label de type (`feat`/`bug`/`enhancement`…) + le label module `app:<module>`
  (lister au besoin : `gh label list`).
- Récupérer le numéro d'issue retourné (`#N`) — il servira au commit.

### 5. Implémenter en TDD
Par défaut, **test d'abord** (venv requis : `source venv/bin/activate`) :
1. Écrire le(s) test(s) qui échoue(nt) et cadrent le comportement attendu.
2. Implémenter le minimum pour les faire passer.
3. Refactorer si utile, tests toujours verts.

Backend → `pytest apps/<app>/`. Front critique → E2E Playwright ou test ciblé.
Déléguer si pertinent aux agents `django-drf-test-writer` / `playwright-e2e-writer`.

**Exceptions au TDD** (à ton jugement, à annoncer brièvement) : changement purement
cosmétique/CSS, renommage/typo, wiring de config, ou code non testable unitairement.
Dans ce cas, le dire et vérifier autrement (lint/tsc/vérif manuelle).

### 6. Commit & push (habituel)
Avant le commit, **vérifier que tout est vert** :
```bash
source venv/bin/activate
pytest -q && npm run lint && npx tsc -b ui/tsconfig.json
```
Puis committer et pousser sur `main` :
```bash
git status && git log -1          # ⚠️ sessions parallèles : rien de stagé par autrui, bonne branche
git add <fichiers ciblés>         # jamais .env*, venv, .claude/, htmlcov
git commit -m "<type>(<app>): <description> (#N)

- point concis
- point concis

Closes #N"
git push origin main
```
- Message conventionnel `<type>(<app>): <description> (#N)` — alimente le changelog
  (voir `CLAUDE.md` : `feat`/`fix`/`perf` visibles ; toujours un scope).
- `Closes #N` dans le corps ferme l'issue automatiquement au push sur `main`.
- **Aucune signature.**
- Ne stager que les fichiers du changement (`git add` ciblé, jamais `git add -A` à l'aveugle).

### 7. Vérifier la fermeture de l'issue
Après le push :
```bash
gh issue view N --json state -q .state    # doit être CLOSED
```
Si l'issue n'est pas fermée (ex. le `Closes` n'a pas matché), la fermer explicitement :
```bash
gh issue close N -c "Livré sur main dans <sha>."
```

## Garde-fous
- Si à l'implémentation le changement se révèle plus large ou risqué que prévu →
  s'arrêter, le dire, et basculer sur une branche + `/ship` (flow PR).
- Ne jamais pousser du rouge sur `main`.
- Si la session tourne dans le checkout principal partagé, redoubler de prudence au
  commit (sessions parallèles).

---
name: bug
description: Corriger un bug de bout en bout — reproduire, isoler la cause racine, écrire un test de régression qui échoue, corriger, vérifier, livrer. Crée une issue GitHub (label bug) de suivi, fermée à la livraison. Utiliser quand l'utilisateur signale un comportement cassé, une erreur, une régression.
allowed-tools: Bash, Read, Edit, Write, Glob, Grep
---

# Bug — reproduire, tester, corriger, livrer

Cycle de correction de bug centré sur **la cause racine** et **le non-retour** :
un bug corrigé sans test de régression revient. La règle d'or : **d'abord un test
qui reproduit et échoue, ensuite le fix**.

## Règles absolues

1. **Ne jamais signer le travail** : pas de `Co-Authored-By`, pas de « Generated with
   Claude Code ». Prime sur tout défaut.
2. **Cause racine, pas symptôme.** Ne pas masquer l'erreur (try/except large, garde
   défensive qui cache le vrai problème). Comprendre *pourquoi* ça casse avant de toucher.
3. **`main` = déploiement prod auto** → tout vert avant push. Rien de rouge sur `main`.

## Flow

### 1. Cerner le bug
Reformuler : quel comportement observé vs attendu, dans quel contexte. Rassembler
les indices donnés (message d'erreur, trace, étapes). Si l'info manque pour reproduire,
poser **une** question ciblée.

### 2. Reproduire
Reproduire le bug de façon déterministe **avant** de chercher le fix :
- Backend : test/`pytest` ciblé, `python manage.py shell`, ou log.
- Front : E2E Playwright, ou repro manuelle (`/dev` puis navigateur).
- Chercher la source (Grep/Glob/Read) et **formuler l'hypothèse de cause racine**.

Si le bug n'est pas reproductible, le dire et proposer comment instrumenter — ne pas
corriger à l'aveugle.

### 3. Créer l'issue GitHub (suivi)
Sur `jammindev/maisonnee`, **avant** le fix :
```bash
gh issue create \
  --title "fix(<app>): <symptôme court>" \
  --label "bug" --label "app:<module>" \
  --body "**Observé** : …
**Attendu** : …
**Repro** : …
**Cause racine (hypothèse)** : …"
```
- Ajouter `--label "blocker"` si le bug empêche un usage clé de l'app.
- Récupérer le numéro `#N` (servira au commit).

### 4. Test de régression (échoue d'abord)
Écrire le test qui **capture le bug** et **échoue** sur le code actuel — c'est la
preuve qu'on a bien cerné le problème, et le garde-fou anti-retour :
```bash
source venv/bin/activate
pytest apps/<app>/ -k "<nouveau_test>"    # doit être ROUGE
```
Déléguer si utile à `django-drf-test-writer` (backend) / `playwright-e2e-writer` (front).

**Exception** (à ton jugement, à annoncer) : bug purement visuel/CSS ou non testable
unitairement → pas de test auto, mais vérif manuelle documentée (avant/après).

### 5. Corriger
Appliquer le correctif minimal qui traite la cause racine. Le test de régression
passe désormais :
```bash
pytest apps/<app>/ -k "<nouveau_test>"    # doit être VERT
```

### 6. Vérifier globalement
Aucune régression ailleurs :
```bash
source venv/bin/activate
pytest -q && npm run lint && npx tsc -b ui/tsconfig.json
```

### 7. Livrer — arbitrage direct main vs PR
- **Bug trivial / isolé** (une ligne, typo, garde manquante, scope clair) →
  commit direct sur `main` (autorisé par `CLAUDE.md` pour les micro-bugs) :
  ```bash
  git status && git log -1        # ⚠️ sessions parallèles
  git add <fichiers ciblés>       # jamais .env*, venv, .claude/, htmlcov
  git commit -m "fix(<app>): <description> (#N)

  - cause : …
  - fix : …

  Closes #N"
  git push origin main
  ```
- **Bug non-trivial** (touche plusieurs modules, changement de logique, risque de
  régression) → branche `fix/<app>-<desc>` + PR via le skill `/ship` (checks CI +
  revue manuelle). Le commit garde `Closes #N`.

Message conventionnel `fix(<app>): … (#N)` (alimente le changelog). **Aucune signature.**

### 8. Vérifier la fermeture de l'issue
```bash
gh issue view N --json state -q .state    # CLOSED
```
Sinon la fermer explicitement :
```bash
gh issue close N -c "Corrigé dans <sha>. Test de régression : <chemin>."
```

## Garde-fous
- Pas de test de régression rouge d'abord = on ne sait pas si on corrige le bon truc.
- Si la cause racine reste floue après investigation → s'arrêter et remonter ce qu'on
  sait, plutôt que de patcher au hasard.
- Si le fix s'avère large/risqué → PR (`/ship`), pas de push direct sur `main`.

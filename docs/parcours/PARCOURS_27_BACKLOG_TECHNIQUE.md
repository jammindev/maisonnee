# Parcours 27 — Backlog technique V1

> **V1 livrée le 2026-07-28** — cadrage et implémentation le même jour, en 4 PR
> (#443 lots 1-3, #444 lot 4, #445 lot 5, #447 lot 6). Fiche module :
> `docs/MODULES/recap.md`.
>
> Cadrage réalisé le 2026-07-28. Chantier **métier** : le récap mensuel raconté du
> foyer — une story de cartes, un chapitre par module, adossée au mécanisme
> d'instantané figé du bilan budgétaire (parcours 21).

## Tableau de bord

**Issue ombrelle : [#435](https://github.com/jammindev/maisonnee/issues/435)**

| Lot | Sujet | Statut | Issue |
|---|---|---|---|
| 1 | Socle `apps/recap` — modèle `HouseholdRecap`, registre `CHAPTER_SPECS`, instantané figé, chapitre Argent | ✅ Livré (#443) | #436 |
| 2 | Rendu localisé + vernis IA (`render.py`, `polish.py`, mémoïsation par langue) | ✅ Livré (#443) | #437 |
| 3 | API de lecture (`/api/recap/`, historique + mois + `latest`) | ✅ Livré (#443) | #438 |
| 4 | La story — frontend `/app/recap`, cartes séquencées, historique, i18n | ✅ Livré (#444) | #439 |
| 5 | Les quatre autres chapitres — accompli, maison, souvenirs | ✅ Livré (#445) | #440 |
| 6 | Le rendez-vous — `PingSpec` du 1er, carte dashboard, préférences de chapitres | ✅ Livré (#447) | #441 |

## Doc associée

- Doc produit : [PARCOURS_27_LE_RECAP_MENSUEL_RACONTE.md](./PARCOURS_27_LE_RECAP_MENSUEL_RACONTE.md)
- Fiche concept : [../fiches/SNAPSHOT_ET_RECIT.md](../fiches/SNAPSHOT_ET_RECIT.md)
- **Pattern de référence n°1 — l'instantané** : `apps/budget/report/` (`stats.py`
  calcul figé, `service.py` get-or-generate + mémoïsation, `render.py` déterministe
  localisé, `polish.py` vernis facultatif, `ping.py` rendez-vous). À lire en entier
  avant de commencer : la V1 est cette architecture élargie, pas une nouvelle.
- **Pattern de référence n°2 — le registre de collecteurs** : `apps/agent/digest/`
  (`collectors.py` : `SectionSpec`, gating module, imports paresseux, isolation des
  pannes). Attention : contrat de collecteur **différent** (voir décisions).
- `apps/pings/registry.py` — `PingSpec` (opt-in, heure locale, `PingLog` idempotent,
  fuseau, langue, gating module).
- CLAUDE.md, sections « Le fuseau du foyer — `core.timezones` », « Pattern standard —
  Feature page », « Montants — un seul formatter ».
- Mémoire projet : `engagement-strategy-house` — pourquoi aucun chiffre par membre.

## Flow cible

1. Le 1er du mois, un membre ouvre House → une carte **« Juillet est prêt »** est en
   tête du dashboard. En parallèle, ceux qui ont activé le ping reçoivent sur Telegram
   un teaser + lien.
2. Il ouvre `/app/recap/2026-07` → la story démarre : une carte plein écran, un gros
   chiffre, une phrase. Il fait défiler.
3. **Au premier accès du mois clos, l'instantané est calculé et gelé** : chaque
   chapitre dont le module est actif produit ses cartes ; le chapitre Argent lit le
   `BudgetReport` déjà gelé sans resommer.
4. Le texte de chaque carte est **rendu à la lecture** dans la langue du lecteur
   (gabarit déterministe), éventuellement repoli par Claude et mémoïsé.
5. `/app/recap` liste l'historique — sobre, une ligne par mois, sans mise en scène.

## Décisions de cadrage

- **Une nouvelle app `apps/recap/`, pas une extension de `budget`.** L'argent est un
  chapitre parmi quatre ; mettre le récap du foyer dans le module budgets
  l'attacherait au mauvais domaine et le rendrait dépendant d'un module métier. Le
  récap **consomme** `budget`, `tasks`, `projects`, `chickens`, `electricity`, `water`,
  `documents` — il n'appartient à aucun. Modèle household-scoped, comme tout le reste.
- **Le récap coexiste avec le bilan budgétaire, il ne le remplace pas.**
  `/app/money/reports` reste : c'est l'artefact chiffré de l'argent, utile pour
  lui-même. Le chapitre Argent du récap **lit** son instantané via
  `budget.report.service.get_or_generate_report` — jamais `compute_month_stats`
  directement, jamais un `Sum` maison. *Un compteur ne peut pas avoir deux
  définitions.*
- **Le contrat de collecteur est « données », pas « phrases ».** Un `ChapterSpec.collect`
  renvoie des cartes **sans un mot de langue** (nombres, `str(Decimal)`, clés
  techniques, noms propres saisis par l'utilisateur). C'est la différence de fond avec
  `digest.SECTION_SPECS`, dont les collecteurs traduisent à la collecte. Copier un
  collecteur de digest tel quel gèlerait la langue de l'auteur dans l'historique.
- **Un instantané gelé est un format public : on ajoute des clés, on n'en renomme
  jamais.** Un chapitre livré après coup n'apparaît pas dans les mois déjà gelés, et le
  rendu traite un chapitre inconnu exactement comme un chapitre absent — sans lever.
  Même discipline que le `"amount": null | "400.00"` de `budget/report/render.py`.
- **Aucun chiffre par membre, jamais.** Les chapitres agrègent au niveau du foyer. Il
  est interdit de grouper par `assigned_to` / `created_by` / `logged_by`. Test de
  régression nommé dans la définition de done.
- **Un instantané de foyer exclut le privé au calcul, pas à l'affichage.** Il est gelé
  une fois et lu par tous les membres : `Task.is_private=True` est **exclu du
  comptage**, pas filtré au rendu. C'est le piège exact de la reprise d'un collecteur
  de digest, qui lui peut filtrer par destinataire (`Q(is_private=False) | Q(created_by=user)`).
- **Bornes de mois via `core.timezones`** — en réutilisant
  `budget.report.stats.month_bounds(household, "YYYY-MM")` et `previous_month`. Jamais
  `date.today()`, jamais `timezone.localdate()`, jamais un `ZoneInfo` local. La borne
  d'un mois décide de quel mois relève un fait.
- **Un récap pauvre ne part pas.** Sous un seuil de cartes (`RECAP_MIN_CARDS`, défaut
  3), l'instantané est calculé et stocké mais **le ping ne part pas et la carte
  dashboard ne s'affiche pas** — miroir du `if not expense_count: return None` du ping
  budgétaire. Un rendez-vous qui livre du vide use le rendez-vous.
- **Le ping est un teaser + lien, pas le récap.** Une story se regarde. Le ping porte
  le titre du mois, une ou deux accroches, et l'URL. Conséquence à assumer : un
  utilisateur qui a activé **et** le bilan budgétaire **et** le récap reçoit deux
  messages le 1er ; `monthly_recap` est donc **désactivé par défaut** et la page
  Réglages le dit.
- **Pas de rattrapage historique.** Aucune command de backfill : le récap commence au
  premier mois clos après la livraison. Les premiers mois d'un foyer sont incomplets et
  produiraient des récaps faux.
- **Le module `recap` est core (non désactivable)**, comme `money` : il ne porte aucune
  donnée propre et se vide tout seul quand les modules sources sont coupés. Un foyer
  qui a désactivé les quatre chapitres n'obtient simplement pas de récap (seuil).

## Lot 1 — Socle `apps/recap` (#436)

### But

Poser l'app, le modèle d'instantané et le registre de chapitres, avec **un seul**
chapitre (Argent) — celui qui ne demande aucun agrégat nouveau. Livrable : un
instantané gelé, vérifiable en shell.

### Modèle

- **`HouseholdRecap`** (`HouseholdScopedModel`, PK UUID, table `household_recaps`) :
  `month` CharField(7) « YYYY-MM », `stats` JSONField(default=dict).
  `UniqueConstraint(household, month, name='unique_recap_per_month')`,
  `ordering = ['-month']`, `HouseholdScopedManager`. Décalque volontaire de
  `budget.models.BudgetReport` (`apps/budget/models.py:153`).

### Forme de `stats`

Sans un mot de langue. `chapters` est une **liste ordonnée** — l'ordre du récit est
figé avec lui :

```
{
  "month": "2026-07",
  "generated_for": ["money", "achievements", ...],   # chapitres collectés
  "chapters": [
    {"key": "money", "cards": [
        {"kind": "total_spent", "value": "1240.50", "trend_pct": -12.4,
         "prev": "1415.00"},
        ...
    ]},
    ...
  ],
  "card_count": 6
}
```

### Fichiers

- `apps/recap/` — app complète : `__init__.py`, `apps.py`, `models.py`, `migrations/`,
  `admin.py` (lecture seule), `chapters.py`, `service.py`, `tests/`.
- `apps/recap/chapters.py` — `RecapCard` (dataclass : `kind`, `payload: dict`),
  `Chapter` (dataclass : `key`, `cards: list[RecapCard]`),
  `ChapterSpec` (frozen dataclass : `key`, `module: str | None`,
  `collect: Callable[..., Chapter | None]`), `CHAPTER_SPECS`, `CHAPTER_KEYS`,
  `active_chapter_specs(household)` (gating `Household.disabled_modules`),
  et `collect_money` — qui appelle
  `budget.report.service.get_or_generate_report(household, month)` puis **lit** son
  `stats`. Imports des apps sources **paresseux** dans chaque collecteur.
- `apps/recap/service.py` — `last_closed_month(household)`,
  `get_or_generate_recap(household, month) -> HouseholdRecap` (get-or-create
  idempotent, `IntegrityError` → re-fetch, jamais de recalcul d'un instantané
  existant), `build_stats(household, month, *, disabled_chapters=())` (assemble,
  **isole** un collecteur qui lève via `logger.exception` et continue).
- `config/settings/base.py` — `INSTALLED_APPS` + `RECAP_MIN_CARDS = 3`,
  `RECAP_AI_POLISH_ENABLED = False`.

### Critères

- Un mois clos produit un instantané, une seule fois : deux appels renvoient le même
  objet, `stats` inchangé (test d'idempotence + test « une édition de dépense après
  gel ne change pas le récap »).
- Le chapitre Argent est **identique** aux chiffres du `BudgetReport` du même mois
  (test d'accord), et aucun `Sum` n'est écrit dans `apps/recap/`.
- Un collecteur qui lève ne coule pas l'instantané : les autres chapitres sont là,
  l'exception est loguée.
- Module désactivé → chapitre **absent** de `chapters` et de `generated_for`, pas vide.
- Bornes de mois obtenues via `budget.report.stats.month_bounds` ; aucun
  `date.today()` / `ZoneInfo` dans l'app.

## Lot 2 — Rendu localisé + vernis IA (#437)

### But

Transformer l'instantané en cartes lisibles dans la langue du lecteur. Décalque de
`budget/report/render.py` + `polish.py`.

### Fichiers

- `apps/recap/render.py` — `render_card(card: dict) -> dict` (→ `{kind, emoji, headline,
  value, caption}`, tout localisé via `gettext`), `render_chapters(stats) -> list[dict]`.
  Doit **ignorer silencieusement** un `kind` inconnu et tolérer une clé manquante.
  Montants formatés comme `budget/report/render.py::_money`.
- `apps/recap/polish.py` — `polish_recap(cards) -> list[str] | None` : repolit les
  `caption` (jamais les chiffres), renvoie `None` sur toute anomalie, gardé par
  `RECAP_AI_POLISH_ENABLED`. Miroir de `budget/report/polish.py` et
  `releases.polish_descriptions`.
- `apps/recap/service.py` — `render_recap(recap, *, lang=None, polish=True)` :
  `translation.override(lang)`, cache dans `stats['_polished'][lang]`, écriture via
  `save(update_fields=['stats', 'updated_at'])` en **copiant** les dicts imbriqués
  (piège d'aliasing déjà commenté dans `budget/report/service.py:72`).
- `locale/{fr,de,es}/LC_MESSAGES/django.po` — nouvelles chaînes + `compilemessages`.

### Critères

- Le gabarit déterministe rend les quatre langues sans jamais appeler le réseau.
- Vernis coupé, indisponible ou en erreur → le déterministe sort, aucune exception ne
  remonte.
- Deux rendus dans la même langue = **un seul** appel LLM (mémoïsation vérifiée).
- Un instantané portant un `kind` inconnu se rend sans lever (test de compatibilité
  ascendante, à garder pour toujours).

## Lot 3 — API de lecture (#438)

### But

Exposer l'historique et un mois. Lecture seule — un récap ne s'édite pas.

### Fichiers

- `apps/recap/serializers.py` — `HouseholdRecapSerializer` : `id`, `month`,
  `card_count`, `chapters` (rendus via `render_recap`, langue de la requête),
  `created_at`. Le `stats` brut n'est pas exposé.
- `apps/recap/views.py` — `HouseholdRecapViewSet(ReadOnlyModelViewSet)`,
  `IsHouseholdMember`, `for_user_households`, lookup par `month` ; action
  `latest` (→ dernier mois clos, **génère** si absent, 204 si sous le seuil).
- `apps/recap/urls.py` + `config/urls.py` — `/api/recap/`.
- `ui/src/gen/api` — `npm run gen:api:refresh`.

### Critères

- `GET /api/recap/` = historique du foyer, ordre décroissant, cloisonné au foyer
  (test d'isolation inter-foyers).
- `GET /api/recap/latest/` génère l'instantané au premier appel, le relit ensuite.
- La langue du rendu suit celle de la requête ; deux langues → deux textes, un seul
  instantané.

## Lot 4 — La story (frontend) (#439)

### But

La mise en scène : cartes séquencées plein écran. C'est le lot où se joue l'effet
produit.

### Fichiers

- `ui/src/features/recap/hooks.ts` — `recapKeys` (factory), `useLatestRecap`,
  `useRecap(month)`, `useRecapHistory`.
- `ui/src/features/recap/RecapStoryPage.tsx` — route `/app/recap/:month`. Défilement
  carte par carte (clavier ←/→, swipe tactile, clic), indicateur de progression,
  sortie explicite. Pas d'auto-play : un récap n'est pas une publicité.
- `ui/src/features/recap/RecapCardView.tsx` — une carte : emoji, gros chiffre,
  accroche, légende. Montants via `formatAmount` de `@/lib/format` — **jamais** un
  `toFixed()` ni un `Intl` inline.
- `ui/src/features/recap/RecapHistoryPage.tsx` — route `/app/recap`, liste sobre par
  mois + `EmptyState` (« votre premier récap arrivera le 1er »).
- `ui/src/lib/api/recap.ts`, route + entrée sidebar (groupe **Compte**, à côté de
  Digest), `ui/src/locales/{en,fr,de,es}.json` → namespace `recap`.

### Critères

- Zéro couleur codée en dur : tokens du design-system uniquement.
- Zéro `defaultValue` dans les `t()` ; les quatre catalogues ont les mêmes clés
  (`ui/src/locales/keys.test.ts` vert).
- Lisible au clavier et au doigt ; le contenu large scrolle dans son conteneur, la
  page ne scrolle jamais horizontalement.
- `npm run lint` propre, `tsc -b` sans erreur.

## Lot 5 — Les quatre autres chapitres (#440)

### But

L'élargissement. Chaque chapitre est un collecteur indépendant, aveugle aux autres,
adossé au **service** de son app source — jamais à un ORM dupliqué.

### Fichiers — `apps/recap/chapters.py`

- `collect_achievements` (module `None`, core) — tâches terminées dans le mois
  (`Task.completed_at` dans les bornes, `status=DONE`), **`is_private=True` exclu**,
  et avancement des chantiers : projets actifs ayant au moins une tâche terminée dans
  le mois. Aucun groupement par membre.
- `collect_home` (chapitres conditionnés module par module) — œufs via
  `chickens.services.egg_stats`, électricité via
  `electricity.services.consumption_summary`, eau via
  `water.services.consumption_summary`. Chaque source absente ou sans historique →
  carte absente, pas une carte à zéro.
- `collect_memories` (module `photos`) — `documents.Document` de type `photo` créés
  dans le mois. **Stocke des ids, pas des URLs** (une URL signée expire, l'instantané
  est éternel) ; le rendu résout et **dégrade proprement** si une photo a été
  supprimée depuis.
- `CHAPTER_SPECS` complété dans l'ordre du récit ; `render.py` étendu ; clés i18n des
  nouveaux `kind` dans les 4 `.po`.

### Critères

- Une tâche privée n'est **jamais** comptée (test explicite).
- Aucun chapitre ne ventile par membre — test
  `test_the_recap_never_breaks_down_by_member` (grep interdisant `assigned_to` /
  `created_by` dans les `values()` / `annotate()` de l'app).
- Chaque module désactivé retire ses cartes sans toucher aux autres.
- Une photo supprimée après le gel ne casse ni le rendu ni l'API.
- Tendances calculées contre le mois précédent avec les mêmes bornes fuseau.

## Lot 6 — Le rendez-vous (#441)

### But

Faire en sorte que le récap se **trouve** sans être cherché.

### Fichiers

- `apps/recap/ping.py` — `build_monthly_recap_message(household, user, *, today)` :
  `None` si `today.day != 1`, sinon `get_or_generate_recap(last_closed_month(...))`,
  `None` si `card_count < RECAP_MIN_CARDS`, sinon **teaser + lien** (titre du mois, une
  ou deux accroches, URL `/app/recap/<month>`). HTML échappé, calqué sur
  `budget/report/ping.py`.
- `apps/recap/apps.py::ready()` — `register(PingSpec('monthly_recap',
  build_monthly_recap_message, default_send_at=time(9, 0), module=None))`.
- `ui/src/features/dashboard/RecapTeaserCard.tsx` + montage dans `DashboardPage` — en
  tête, uniquement quand un récap frais existe et n'a pas été ouvert. Le « vu » vit
  côté client (`useSessionState`/local) — pas de table pour ça en V1.
- `apps/accounts/models.py` + `serializers.py` — `recap_disabled_chapters`
  (JSONField, validation de **forme** uniquement, miroir exact de
  `digest_disabled_sections`, `apps/accounts/models.py:146`).
- Réglages : les toggles de chapitres + la mention explicite du doublon possible avec
  le bilan budgétaire du 1er.

### Critères

- Le ping ne part que le 1er, une seule fois (idempotence `PingLog`), dans la langue et
  le fuseau du destinataire.
- Sous le seuil de cartes : aucun ping, aucune carte dashboard — et l'instantané existe
  quand même (consultable depuis `/app/recap`).
- `monthly_recap` est **off par défaut**.
- Couper un chapitre dans les préférences le retire du rendu ; il reste dans
  l'instantané gelé (préférence de lecture, pas de calcul).

## Ordre recommandé d'implémentation

**1 → 2 → 3 → 4** en tranche verticale : à la fin du lot 4, la story tourne pour de
vrai avec un seul chapitre. C'est là qu'on juge la forme — et c'est réversible à peu de
frais. **Puis 5** (l'élargissement, sans risque de conception), **puis 6** (le
rendez-vous, qui n'a de sens qu'une fois qu'il y a quelque chose à annoncer).

Ne pas inverser 4 et 5 : quatre chapitres écrits contre une mise en scène pas encore
validée sont quatre chapitres à réécrire.

## Points de vigilance

- **Ne pas copier un collecteur de digest.** Deux pièges à la fois : la traduction à la
  collecte (qui gèlerait la langue) et le filtrage par destinataire (qui ne veut rien
  dire dans un instantané de foyer).
- **Ne jamais recalculer l'argent.** Le chapitre Argent lit le `BudgetReport`. Un
  `Sum("amount")` dans `apps/recap/` est un bug de conception, pas un raccourci.
- **`stats` est éternel.** Toute évolution ajoute des clés. Le rendu doit survivre à un
  instantané écrit par une version antérieure du code — pour toujours.
- **Aliasing de dict imbriqué** lors de l'écriture du cache `_polished` : copier, comme
  `budget/report/service.py` le fait explicitement.
- **Le seuil de cartes protège le rendez-vous**, pas la performance. Ne pas le
  contourner « pour tester » en prod.
- **Coût du gel** : `get_or_generate_recap` déclenche N collecteurs. Il est appelé par
  `latest`, par le ping et par la carte dashboard — s'assurer qu'un mois déjà gelé est
  un simple `SELECT`, et que le tick du scheduler ne recalcule rien.
- **Le récap est un candidat évident à la sur-ingénierie.** Pas d'animations lourdes,
  pas de lib de charts, pas de moteur de templates. Un gros chiffre et une phrase.

## Définition de done technique

1. `pytest` vert, y compris les tests de régression nommés :
   accord chapitre Argent ↔ `BudgetReport`, idempotence du gel, tolérance à un `kind`
   inconnu, exclusion des tâches privées, `test_the_recap_never_breaks_down_by_member`.
2. i18n **4 langues** complètes (front `recap` + `.po` back), aucun `defaultValue`,
   `ui/src/locales/keys.test.ts` vert, `compilemessages` passé.
3. `npm run lint` propre et `tsc -b` sans erreur (`--noEmit` ne voit rien sur le
   tsconfig solution).
4. `npm run gen:api:refresh` rejoué, types commités.
5. Aucune couleur codée en dur ; `formatAmount` pour tout montant ; `todayISO` /
   `toLocalISODate` pour toute date de calendrier.
6. **Fiche module `docs/MODULES/recap.md` créée** (rôle, état synthétique, « ajouter un
   chapitre en ~10 lignes », pourquoi ce design, limites V1) et
   `docs/MODULES/README.md` mise à jour.
7. **Tutoriels à jour** — skill `/tutorials` : le récap change le parcours utilisateur
   (nouvelle page, nouveau rendez-vous, nouvelle préférence).
8. `docs/fiches/README.md` référence `SNAPSHOT_ET_RECIT.md` ; `budget.md` et
   `digest.md` renvoient vers le récap.
9. Tableau de bord de ce backlog à jour (statuts + n° de PR).

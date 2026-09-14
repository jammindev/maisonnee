"""Le produit s'appelle Maisonnée, et une seule fois — partout où on le lit.

Le dépôt a été renommé le 2026-08-18 (`house` → `maisonnee`) par recherche et
remplacement. Trois jours plus tard, huit surfaces disaient encore « House », et
c'est l'utilisateur qui l'a signalé — pas la CI :

- le titre de la **notification push de test** (`apps/webpush/views.py`), donc le
  seul écran où l'on va justement vérifier que les notifications marchent ;
- la **page de maintenance** de nginx, servie à chaque visiteur pendant un deploy,
  dans son `<title>` et son `<h1>` ;
- le **JSON 503** de nginx, que l'intercepteur axios affiche en toast — « House est
  momentanément indisponible » ;
- le **sujet de l'e-mail de réinitialisation**, et là c'était pire qu'un mot périmé
  (voir `test_prose_is_translated.py`, entrée `apps/accounts/views/api.py`) ;
- la planche d'étiquettes de zones (`printIntro`) dans les **quatre** locales ;
- et, à l'inverse, un thème de couleur devenu « Maisonnée » en anglais alors que
  les seize autres sont des couleurs — le remplacement avait mordu trop large.

**Pourquoi un test et pas une relecture.** Un renommage est le cas d'école du
travail à sortir de l'espace latent : la question « reste-t-il une occurrence ? » a
la même bonne réponse à chaque fois, par définition, et elle se calcule. En revue,
un fichier qui a été renommé ressemble exactement à un fichier qui ne l'a pas été —
il n'y a rien à voir dans le diff, puisque le défaut est une **absence** de diff.
C'est la même famille que `keys.test.ts` et `test_registry.py`.

**Limite déclarée, et assumée.** Ce test ne balaye pas tout le Python. Une
quarantaine de docstrings et de commentaires internes disent encore « House »
(`apps/banking/anchoring.py`, `apps/banking/services.py`…) : c'est de la prose de
raisonnement, personne ne la lit dans l'app, et l'inclure rendrait ce contrôle
rouge en permanence — donc inutile, exactement comme les `help_text` exclus de
`test_prose_is_translated.py`. Le Python **user-facing** est couvert autrement, et
des deux côtés : ce qui passe par `gettext` est vu ici via les catalogues `.po`, et
les modules qui écrivent au foyer sans passer par eux sont listés dans
``USER_FACING_PYTHON``.
"""
import re
from pathlib import Path

import pytest
from django.conf import settings

#: Le nom du produit. Toute autre orthographe dans une surface lue par un
#: utilisateur est un reste de renommage.
PRODUCT_NAME = "Maisonnée"

#: L'ancien nom, en tant que **mot** : `Household` et `households` sont des termes
#: du domaine et n'ont rien à voir. Le `(?!hold)` est ce qui sépare les deux.
FORMER_NAME = re.compile(r"\bHouse(?!hold)\b")

#: Les surfaces non-Python que l'utilisateur lit. Les catalogues `.po` sont dedans
#: parce qu'un `msgid` est une chaîne de production : c'est ce que voit celui dont
#: la langue n'est pas traduite.
USER_FACING_ASSETS = (
    "ui/src/locales/en/translation.json",
    "ui/src/locales/fr/translation.json",
    "ui/src/locales/de/translation.json",
    "ui/src/locales/es/translation.json",
    "templates/manifest.json",
    "templates/sw.js",
    "nginx/html/maintenance.html",
    "nginx/conf.d/default.conf",
    "apps/accounts/templates/accounts/emails/password_reset.txt",
    "apps/accounts/templates/accounts/emails/password_reset.html",
    "locale/fr/LC_MESSAGES/django.po",
    "locale/de/LC_MESSAGES/django.po",
    "locale/es/LC_MESSAGES/django.po",
    # Le schéma OpenAPI est lu par l'inconnu qui découvre l'API d'un dépôt public.
    "config/settings/base.py",
)

#: Les modules Python qui écrivent au foyer — soit sans passer par `gettext`
#: (`webpush`), soit en le traversant (`telegram`, `notifications`). Aucun ne
#: contient de prose de raisonnement : les balayer entièrement est sans bruit, et
#: c'est ce qui les rend scannables là où `apps/banking/` ne l'est pas.
USER_FACING_PYTHON = (
    "apps/webpush/views.py",
    "apps/notifications/service.py",
    "apps/telegram/service.py",
)

#: Les occurrences où « House » **n'est pas** le nom du produit, par fichier.
#:
#: Écarter n'est pas cacher : chaque entrée porte son motif, comme un
#: `ComplianceWaiver`. Une seule à ce jour, et elle est instructive — c'est le
#: renommage qui l'avait cassée dans l'autre sens. `theme-house` est l'un des
#: dix-sept thèmes de couleur de `ui/src/styles/themes.css`, et les seize autres
#: sont des couleurs ou des ambiances (Blue, Sage, Midnight…). Le remplacement
#: global l'avait rebaptisé « Maisonnée » en anglais seulement : un thème sur
#: dix-sept se présentait comme *le* thème du produit, alors que le français,
#: l'allemand et l'espagnol disaient « Maison », « Haus », « Casa ».
ALLOWED = {
    "ui/src/locales/en/translation.json": (
        '"colorThemeHouse": "House"',
    ),
}


def _read(relative: str) -> str:
    return (Path(settings.BASE_DIR) / relative).read_text(encoding="utf-8")


@pytest.mark.parametrize("relative", USER_FACING_ASSETS + USER_FACING_PYTHON)
def test_no_user_facing_surface_still_says_house(relative):
    """Aucune surface lue par un utilisateur ne porte l'ancien nom du produit."""
    allowed = ALLOWED.get(relative, ())
    offenders = [
        f"    ligne {number} : {line.strip()[:110]}"
        for number, line in enumerate(_read(relative).splitlines(), start=1)
        if FORMER_NAME.search(line)
        and not any(exception in line for exception in allowed)
    ]
    assert not offenders, (
        f"{relative} dit encore « House » là où l'utilisateur le lit :\n"
        + "\n".join(offenders)
        + f"\n  Le produit s'appelle {PRODUCT_NAME}. Si l'occurrence est un terme du "
        "domaine et non le nom du produit, c'est le motif qu'il faut affiner, pas "
        "l'assertion qu'il faut contourner."
    )


#: Les commentaires — toutes syntaxes du front confondues. Une ligne qui commence
#: par l'un de ces préfixes est de la prose de raisonnement, hors périmètre pour la
#: même raison que les docstrings Python : douze d'entre elles disent « House » dans
#: `apps/banking/` côté front, et les inclure rendrait le contrôle rouge à vie.
_COMMENT = ("*", "//", "/*", "{/*")


def test_no_frontend_code_names_the_old_product():
    """Le titre d'onglet de **toutes** les pages disait « — House ».

    Trouvé en ouvrant l'app, pas par ce test : la première version ne balayait que
    les catalogues, les templates et nginx. Or `ui/src/components/PageHeader.tsx`
    **compose** du texte visible en code (`document.title = ...`), donc il échappait
    aux quatre locales — et c'était la surface la plus exposée de toutes, présente
    sur chaque page, dans chaque onglet, dans chaque favori et dans l'historique du
    navigateur.

    La leçon vaut mieux que le correctif : *une liste de surfaces est une liste, et
    une liste oublie.* D'où un balayage **récursif** du front, avec deux exclusions
    qui ne rotent pas — les commentaires (règle déjà posée pour Python) et
    `ui/src/gen/`, qui est régénéré depuis le schéma OpenAPI et n'est donc pas une
    source à corriger.

    La propriété tenue ici : **aucun code exécutable du front ne nomme le produit en
    dur.** Tout ce que l'utilisateur lit vit dans `ui/src/locales/`, et ce qui est
    composé en code doit l'être depuis une clé i18n ou depuis le nom courant.
    """
    root = Path(settings.BASE_DIR) / "ui" / "src"
    offenders = []
    for path in sorted(root.rglob("*.ts")) + sorted(root.rglob("*.tsx")):
        relative = path.relative_to(Path(settings.BASE_DIR)).as_posix()
        if relative.startswith("ui/src/gen/"):
            continue
        allowed = ALLOWED.get(relative, ())
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            stripped = line.strip()
            if stripped.startswith(_COMMENT):
                continue
            if FORMER_NAME.search(line) and not any(e in line for e in allowed):
                offenders.append(f"    {relative}:{number} : {stripped[:100]}")
    assert not offenders, (
        "du code du front nomme encore « House » :\n"
        + "\n".join(offenders)
        + f"\n  Le produit s'appelle {PRODUCT_NAME}."
    )


def test_every_declared_surface_exists():
    """Un chemin qui a bougé rend le contrôle silencieux, pas rouge.

    Le mode de défaillance de tout test adossé à une liste de chemins : un fichier
    renommé, et l'assertion ne balaye plus rien en restant verte. On lit donc les
    fichiers avant de les scanner — même raison que la vérification de couverture
    de `test_first_run.py`.
    """
    missing = [
        relative
        for relative in USER_FACING_ASSETS + USER_FACING_PYTHON
        if not (Path(settings.BASE_DIR) / relative).is_file()
    ]
    assert not missing, f"surfaces déclarées mais introuvables : {missing}"


def test_the_product_name_is_spelled_the_same_everywhere():
    """Le nom apparaît bien, et toujours identique — accent compris.

    Un contrôle qui ne cherche que l'ancien nom passerait sur un fichier vidé, ou
    sur un « Maisonnee » sans accent : le premier ne dit plus rien, le second dit
    autre chose. Trois surfaces suffisent, ce sont celles qui nomment le produit.
    """
    for relative in (
        "templates/manifest.json",
        "nginx/html/maintenance.html",
        "nginx/conf.d/default.conf",
    ):
        content = _read(relative)
        assert PRODUCT_NAME in content, f"{relative} ne nomme plus le produit"
        assert "Maisonnee" not in content.replace(PRODUCT_NAME, ""), (
            f"{relative} écrit « Maisonnee » sans accent"
        )

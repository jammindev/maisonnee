# core/tests/test_prose_is_translated.py
"""
Le foyer ne lit jamais son argent en anglais (issue #543).

Pendant backend de ``ui/src/locales/keys.test.ts``. Le front a son garde-fou depuis
que les ``defaultValue`` ont été bannis ; ``gettext`` n'en avait aucun, et le bilan
mensuel a vécu en production **en anglais dans les quatre langues** : ses quatorze
chaînes avaient un ``msgstr`` vide dans les trois catalogues, ce que gettext traduit
par « renvoie le msgid ». Rien ne plantait, rien n'était rouge, le texte était même
parfaitement valide — simplement pas dans la bonne langue. C'est exactement le défaut
que les ``defaultValue`` produisaient côté front.

**Pourquoi on interroge le catalogue compilé et non le rendu.** Une traduction a le
droit d'être identique à l'original (``%(name)s: %(spent)s.`` est le même texte en
allemand), donc comparer deux rendus ne prouve rien. ``msgfmt`` n'écrit dans le
``.mo`` que les entrées **non vides** : l'appartenance au catalogue est le seul test
exact — et il porte sur ce qui tourne vraiment, pas sur le ``.po`` du dépôt.

**Portée : la prose que le foyer lit.** Pas les ``help_text`` d'admin ni les messages
de validation d'API, dont ~180 restent non traduits et qui sont un autre chantier.
Ce qui est couvert ici est ce qui arrive dans un Telegram ou sur un écran de bilan.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.utils.translation import trans_real

#: Les modules qui composent la prose que le foyer lit. Ajouter un module qui
#: écrit une phrase lue par l'utilisateur, c'est l'ajouter ici.
#:
#: Les quatre ``notifications.py`` sont ici pour une raison plus forte que le
#: bilan mensuel : leur texte est rendu **une fois par destinataire** puis stocké
#: en clair (règle write-time de ``CLAUDE.md``), donc il n'y a aucune seconde
#: chance à l'affichage. Un ``msgstr`` vide ne poste pas une clé brute, il poste
#: une phrase anglaise parfaitement valide dans la cloche d'un foyer francophone
#: — exactement le défaut qu'a vécu ``stock`` en production, et qui ne se voit
#: dans aucune relecture.
PROSE_MODULES = [
    # L'e-mail de réinitialisation et les messages du parcours d'authentification.
    # Ajouté après un défaut qui a vécu en production : le code appelait
    # `_("Reset your House password")` alors que les catalogues portaient
    # `msgid "Reset your Maisonnée password"` — le renommage avait touché les `.po`
    # et pas la source. La recherche ne tombait donc sur **rien**, et l'e-mail
    # partait en anglais, sous l'ancien nom du produit, dans les quatre langues.
    # Un msgid qui dérive de sa source est pire qu'un `msgstr` vide : il n'y a même
    # plus d'entrée à remplir, et le `.po` a l'air complet.
    "apps/accounts/views/api.py",
    "apps/budget/report/render.py",
    "apps/budget/report/ping.py",
    "apps/recap/render.py",
    "apps/recap/ping.py",
    "apps/tasks/notifications.py",
    "apps/interactions/notifications.py",
    "apps/stock/notifications.py",
    "apps/households/notifications.py",
]

LANGUAGES = ["fr", "de", "es"]

#: ``_("…")`` sur une seule ligne — la seule forme utilisée par ces modules, et le
#: test le vérifie plutôt que de le supposer (voir ``test_every_module_yields``).
_LITERAL = re.compile(r'\b_\(\s*"((?:[^"\\]|\\.)*)"')


def _literals(relative_path: str) -> list[str]:
    source = (Path(settings.BASE_DIR) / relative_path).read_text(encoding="utf-8")
    return sorted({m.group(1) for m in _LITERAL.finditer(source) if m.group(1)})


def _catalog(lang: str) -> dict:
    """Le catalogue **compilé** (``.mo``) pour ``lang`` — jamais le ``.po``."""
    return trans_real.translation(lang)._catalog


@pytest.mark.parametrize("module", PROSE_MODULES)
@pytest.mark.parametrize("lang", LANGUAGES)
def test_the_household_never_reads_its_prose_in_english(module, lang):
    catalog = _catalog(lang)
    missing = [s for s in _literals(module) if s not in catalog]

    assert not missing, (
        f"{len(missing)} chaîne(s) de {module} non traduites en {lang} — "
        f"le foyer les lira en anglais.\n"
        + "\n".join(f"  - {s}" for s in missing)
        + f"\n\nCorriger locale/{lang}/LC_MESSAGES/django.po "
        f"puis `python manage.py compilemessages`."
    )


@pytest.mark.parametrize("module", PROSE_MODULES)
def test_every_module_yields_literals(module):
    """Un extracteur qui ne trouve rien rendrait le test du dessus vert à vide —
    la panne silencieuse que ce fichier existe précisément pour interdire."""
    assert _literals(module), f"aucun littéral extrait de {module}"

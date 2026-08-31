"""Qui a le droit de voir quoi — un registre, et un seul point d'application.

``is_private`` veut dire la même chose partout où le champ existe : seul le
déposant voit sa pièce. Cette règle a vécu en **quatre** exemplaires — les
querysets de documents, de tâches et de briefings, plus la permission objet
``core.permissions.CanViewPrivateContent`` — et manquait entièrement à la couche
de retrieval de l'agent, qui ne connaissait que le **foyer**, jamais le
**lecteur**.

Deux définitions d'une même visibilité ne divergent pas symétriquement : c'est
toujours la plus permissive qui l'emporte, et elle le fait en silence.

Ce module tient donc deux choses distinctes, et il faut les garder distinctes :

- ``visible_to_creator`` — **l'implémentation** du couple ``is_private`` /
  ``created_by``. Ce que « privé » veut dire.
- ``REGISTRY`` / ``narrow_for`` — **la déclaration** : quel modèle se restreint
  comment. Ce que chaque app décide pour son modèle.

Pourquoi un registre plutôt qu'un argument passé de main en main
----------------------------------------------------------------

Le drapeau vivait auparavant sur le ``SearchableSpec`` de l'agent, ce qui liait la
confidentialité d'un modèle au fait qu'il soit *cherchable*. Deux limites, et la
seconde est structurelle :

1. Un modèle privatisable non searchable (``briefings.Briefing``) n'avait nulle
   part où se déclarer, et son viewset réécrivait donc la règle à la main.
2. La confidentialité **héritée** — un tracker qui n'a pas de drapeau mais dont le
   projet en a un — ne porte aucun champ. Un catalogue adossé au ``grep`` de
   ``is_private`` ne peut structurellement pas la voir arriver. Le registre, si.

Ce que ce module ne fait PAS
----------------------------

Il **borne des querysets**. Il ne masque rien : remplacer le sujet d'une dépense
par « Dépense privée » est une décision de **sérialisation**, elle vit dans le
serializer et n'a pas sa place ici. La distinction porte un vocabulaire dans ce
dépôt — *cacher* (la ligne disparaît) contre *masquer* (la ligne reste, son
contenu est remplacé) — et les deux moitiés se rangent à deux endroits différents
exprès : ce qui alimente un compteur partagé ne peut pas disparaître d'une liste
sans donner deux définitions au compteur.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from django.db.models import Model, Q, QuerySet


def visible_to_creator(queryset, viewer, *, never_hidden: Q | None = None):
    """Restreindre ``queryset`` à ce que ``viewer`` a le droit de lire.

    Tout ce qui est public, plus les lignes privées dont il est l'auteur.

    ``viewer=None`` — un appel sans utilisateur : évaluation hors ligne, commande
    de fond, test bas niveau — ne voit **que** le public. Le défaut est fermé
    exprès : un chemin qui oublierait de passer le lecteur montre alors moins que
    prévu, jamais plus. Un manque se remarque et se corrige ; une fuite, non.

    Le filtre porte sur ``created_by``, jamais sur le rôle : un owner de foyer
    n'est pas un lecteur privilégié du privé des autres.

    ``never_hidden`` — un sous-ensemble que la confidentialité ne fait jamais
    **disparaître**, déclaré par l'app propriétaire du modèle. Un seul cas existe,
    et il est du métier : une dépense alimente sept agrégations d'argent, donc la
    retirer d'une liste sans la retirer des totaux donnerait deux définitions au
    même compteur. Son secret porte sur le **contenu**, pas sur l'existence.

    Le paramètre est ici, et pas dans un ``Q`` écrit chez l'appelant, pour que la
    règle du lecteur — celle qui ne doit jamais diverger — garde **une** seule
    implémentation. Ce que chaque app décide, c'est son exception ; pas la façon
    de reconnaître un lecteur.
    """
    allowed = Q(is_private=False)
    if viewer is not None and getattr(viewer, "is_authenticated", True):
        allowed |= Q(created_by=viewer)
    if never_hidden is not None:
        allowed |= never_hidden
    return queryset.filter(allowed)


# ── Le registre ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PrivacySpec:
    """Comment la visibilité d'un modèle se restreint, déclaré par son app.

    Même modèle que ``agent.searchables`` et ``banking.compliance.REGISTRY`` :
    **ajouter un mécanisme, c'est ajouter sa déclaration**, et c'est ce qu'on
    vérifie en revue plutôt que de relire chaque queryset du dépôt.
    """

    model: type[Model]
    """Le modèle concerné. Un seul spec par modèle."""

    narrow: Callable[[QuerySet, Any], QuerySet]
    """``(queryset, viewer) -> queryset`` — la restriction.

    Écrite par l'app propriétaire, parce qu'elle seule connaît ses exceptions :
    ``interactions`` sait qu'une dépense ne se cache pas, ``core`` n'a pas à le
    savoir. Pour le couple standard ``is_private`` / ``created_by``, passer
    ``visible_to_creator`` — ne pas en réécrire une variante.
    """


REGISTRY: list[PrivacySpec] = []


def register(spec: PrivacySpec) -> None:
    """Ajouter un spec au registre. Lève si le modèle est déjà déclaré."""
    for existing in REGISTRY:
        if existing.model is spec.model:
            raise ValueError(
                f"PrivacySpec pour {spec.model.__name__} est déjà enregistré"
            )
    REGISTRY.append(spec)


def reset_registry() -> None:
    """Aide de test — vide le registre. Ne pas appeler depuis le code de prod."""
    REGISTRY.clear()


def find_spec(model: type[Model]) -> PrivacySpec | None:
    """Le spec déclaré pour ``model``, ou None s'il n'a pas de confidentialité."""
    for spec in REGISTRY:
        if spec.model is model:
            return spec
    return None


def has_spec(model: type[Model]) -> bool:
    """``model`` a-t-il une restriction de visibilité déclarée ?

    Utile aux appelants qui tiennent des **instances** plutôt qu'un queryset et
    veulent éviter une requête inutile pour les modèles sans confidentialité.
    """
    return find_spec(model) is not None


def narrow_for(queryset: QuerySet, viewer) -> QuerySet:
    """Restreindre ``queryset`` à ce que ``viewer`` a le droit de lire.

    **Le point d'application unique.** Toute porte de lecture passe par ici — la
    liste REST d'un viewset comme les six chemins du retrieval de l'agent (palette
    ⌘K, ``search_household``, ``get_entity``, ``get_related``, ``list_entities``,
    contexte ancré). Un modèle qui déclare sa restriction est donc borné sur
    toutes d'un coup ; l'alternative — un filtre ajouté à chaque site d'appel —
    est exactement la façon dont le scope foyer est resté juste pendant que la
    confidentialité était oubliée.

    Un modèle **non déclaré** ressort inchangé : « pas de spec » veut dire « le
    scope foyer est toute la règle », ce qui est le cas de la grande majorité des
    entités. Ce n'est pas un défaut ouvert — c'est le test de complétude
    (``core/tests/test_privacy_isolation.py``) qui garantit qu'un modèle
    privatisable ne peut pas rester non déclaré.
    """
    spec = find_spec(queryset.model)
    if spec is None:
        return queryset
    return spec.narrow(queryset, viewer)


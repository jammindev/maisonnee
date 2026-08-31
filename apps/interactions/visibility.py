"""Qui voit quelles interactions — une définition, deux portes.

La liste REST (``InteractionViewSet``) et la couche de retrieval de l'agent
(``SearchableSpec.visibility``) doivent répondre la même chose : deux définitions
d'une même visibilité ne divergent pas symétriquement, c'est toujours la plus
permissive qui gagne, et elle le fait en silence. D'où ce module, importé par les
deux, plutôt qu'un ``Q`` recopié dans chacun.

Ce que la règle commune dit — seul le déposant voit sa pièce — vit dans
``core.visibility.visible_to_creator``. Ce que ce module ajoute est l'exception
propre à ce modèle, et il n'y en a qu'une.
"""
from __future__ import annotations

from django.db.models import Q

from core.visibility import visible_to_creator

#: L'argent ne disparaît jamais d'une liste.
#:
#: Une ``Interaction(type="expense")`` alimente ``interactions.queries.expenses()``,
#: point de vérité unique de sept agrégations : barre de budget, ``coverage_ratio``,
#: ``Project.actual_cost``, bilan mensuel figé, détecteurs de conformité. La masquer
#: ici sans la retirer de ces totaux donnerait au budget « Bricolage » deux valeurs
#: selon le lecteur — exactement ce que ``CLAUDE.md`` interdit sous « un compteur ne
#: peut pas avoir deux définitions ».
#:
#: Le secret d'une dépense porte donc sur son **contenu** et non sur son existence :
#: c'est le lot 4 du parcours 33 qui remplacera sujet, fournisseur et projet source
#: par « Dépense privée » pour les autres membres. Masquer, pas cacher.
MONEY_IS_NEVER_HIDDEN = Q(type="expense")


def visible_interactions(queryset, viewer):
    """Restreindre ``queryset`` aux interactions que ``viewer`` a le droit de lire."""
    return visible_to_creator(queryset, viewer, never_hidden=MONEY_IS_NEVER_HIDDEN)

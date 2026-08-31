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


def _belongs_to_a_hidden_project(viewer) -> Q:
    """Les interactions dont la source est un chantier que ``viewer`` ne voit pas."""
    from django.contrib.contenttypes.models import ContentType

    from projects.models import Project
    from projects.visibility import hidden_project_ids

    # ``get_for_model`` est appelé ici et pas au chargement du module : les
    # ContentType vivent en base, et les toucher à l'import casse les migrations
    # sur une base vierge.
    return Q(
        source_content_type=ContentType.objects.get_for_model(Project),
        source_object_id__in=hidden_project_ids(viewer),
    )


def visible_interactions(queryset, viewer):
    """Restreindre ``queryset`` aux interactions que ``viewer`` a le droit de lire.

    Deux sources de confidentialité, et la seconde n'écrit rien nulle part : le
    drapeau propre à l'entrée, et l'héritage d'un chantier privé.

    ⚠️ **L'exception de l'argent vaut pour les deux.** Une dépense de chantier privé
    reste servie comme une dépense privée l'est : elle alimente sept agrégations, et
    la faire disparaître d'une liste sans la retirer des totaux donnerait deux
    définitions au même compteur. Ce qui la protège, c'est le **masquage** de son
    contenu par ``InteractionSerializer`` — sujet, fournisseur et chantier source
    remplacés par « Dépense privée ». Sans quoi le titre du chantier fuirait en clair :
    le sujet auto-généré d'un achat de projet est ``"Achat — {titre du chantier}"``.
    """
    visible = visible_to_creator(queryset, viewer, never_hidden=MONEY_IS_NEVER_HIDDEN)
    return visible.exclude(_belongs_to_a_hidden_project(viewer) & ~Q(type="expense"))


def interaction_is_readable(interaction, viewer) -> bool:
    """Le contenu de cette interaction est-il lisible par ``viewer`` ?

    Ne concerne en pratique que les **dépenses** : tout le reste, ``narrow`` le fait
    déjà disparaître, donc la question ne se pose pas. Une dépense, elle, reste dans
    la liste — et son sujet est ``"Achat — {titre du chantier}"``. Sans cette
    seconde question, privatiser un chantier aurait fait fuiter son titre en clair
    dans la liste des dépenses, dans la ligne bancaire rapprochée et dans les
    citations de l'assistant, c'est-à-dire partout sauf là où on l'avait caché.
    """
    if viewer is not None and getattr(viewer, "is_authenticated", True):
        if interaction.created_by_id == getattr(viewer, "pk", None):
            return True

    if interaction.is_private:
        return False

    # Héritage : la dépense d'un chantier que ce lecteur ne voit pas. À ce point
    # ``is_private`` est faux — une entrée sans chantier source est donc lisible.
    if interaction.source_content_type_id is None or interaction.source_object_id is None:
        return True

    from django.contrib.contenttypes.models import ContentType

    from projects.models import Project

    if interaction.source_content_type_id != ContentType.objects.get_for_model(Project).pk:
        return True
    return not Project.objects.filter(
        pk=interaction.source_object_id, is_private=True
    ).exists()


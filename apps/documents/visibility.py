"""Qui voit quels documents — le drapeau du déposant, et le chantier qui l'héberge.

⚠️ **Conséquence assumée, à connaître avant de rattacher.** Un document lié à un
chantier privé disparaît pour les autres membres, *y compris* s'il est aussi lié à
un équipement partagé. C'est la lecture littérale de « un chantier privé rend privé
tout ce qu'il contient », et c'est le comportement le moins surprenant des deux :
l'autre — ne cacher que les documents dont le chantier privé est l'unique attache —
demanderait au lecteur de savoir combien de liens porte une pièce pour prévoir si
elle va disparaître.

Le geste reste **réversible en un clic** (dé-privatiser le chantier, ou détacher la
pièce), et rien n'est écrit : c'est ce qui rend la règle simple acceptable.
"""
from __future__ import annotations

from core.visibility import visible_to_creator


def visible_documents(queryset, viewer):
    from django.contrib.contenttypes.models import ContentType

    from projects.models import Project
    from projects.visibility import hidden_project_ids

    visible = visible_to_creator(queryset, viewer)
    # Le lien ne porte pas de drapeau : c'est le chantier qu'il désigne qui en a un.
    # ``exclude`` sur une relation inverse retire le document dès qu'**un** de ses
    # liens vise un chantier caché — pas besoin de ``distinct()``, un ``exclude``
    # ne duplique pas les lignes qu'il garde.
    return visible.exclude(
        links__content_type=ContentType.objects.get_for_model(Project),
        links__object_id__in=hidden_project_ids(viewer),
    )

"""Qui voit quelles tâches — le drapeau propre, et celui du chantier."""
from __future__ import annotations

from core.visibility import visible_to_creator


def visible_tasks(queryset, viewer):
    """Restreindre ``queryset`` aux tâches que ``viewer`` a le droit de lire.

    Une tâche est privée par son propre drapeau **ou** parce que son chantier l'est.
    Le second n'écrit rien sur elle : c'est ce qui permet de dé-privatiser un
    chantier sans avoir perdu la trace de ce qui était privé à titre propre, et ce
    qui évite de heurter ``tasks_private_not_assigned`` — une tâche assignée dans un
    chantier qu'on privatise reste assignée, elle devient simplement invisible aux
    autres.
    """
    from projects.visibility import exclude_hidden_projects

    return exclude_hidden_projects(visible_to_creator(queryset, viewer), viewer)

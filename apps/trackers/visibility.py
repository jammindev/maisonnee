"""Qui voit quels trackers — l'héritage du chantier, et rien d'autre.

``Tracker`` ne porte **pas** de champ ``is_private`` : un suivi de valeurs n'a pas
de confidentialité propre. Il en hérite pourtant, parce qu'un tracker « budget
chantier » ou « heures de matériel » nomme le chantier auquel il appartient.

C'est le cas qui a justifié le registre du lot 2 : un modèle dont la visibilité se
restreint **sans porter de drapeau** est invisible pour un catalogue adossé au
``grep`` de ``is_private``. Il fallait un endroit où le déclarer.
"""
from __future__ import annotations


def visible_trackers(queryset, viewer):
    from projects.visibility import exclude_hidden_projects

    return exclude_hidden_projects(queryset, viewer)

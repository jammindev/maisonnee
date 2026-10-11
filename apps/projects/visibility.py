"""La confidentialité d'un chantier, et ce qu'elle entraîne.

Un projet privé rend privé **tout ce qu'il contient** : ses tâches, ses notes, ses
dépenses, ses documents et ses trackers. Trois choses à savoir avant d'y toucher.

**Elle se calcule, elle ne se propage pas.** Aucune écriture sur les enfants : la
visibilité effective vaut ``enfant privé OU projet privé``, évaluée à la lecture.
C'est « le solde n'est jamais dénormalisé » appliqué à la visibilité, et ça achète
trois choses qu'un drapeau recopié perdrait — dé-privatiser rend exactement l'état
d'avant, un enfant créé plus tard hérite sans que personne ait à y penser, et la
contrainte ``tasks_private_not_assigned`` n'est jamais heurtée puisqu'on n'écrit
rien.

**Les zones n'héritent jamais.** Une zone est une pièce de la maison : structurelle,
partagée par vingt features, et sa confidentialité privatiserait la maison. Le
chantier dit *sur quoi* on travaille, la zone dit *où* — seul le premier est un
secret.

**L'argent n'est pas caché, il sera masqué.** Une dépense de projet privé reste dans
les sept agrégations qui la lisent ; c'est son contenu que le serializer remplace.
Voir ``interactions.visibility`` et ``interactions.serializers``.
"""
from __future__ import annotations


def hidden_project_ids(viewer):
    """Les projets privés que ``viewer`` n'a pas le droit de lire.

    Renvoyé comme **queryset de clés** et jamais comme liste matérialisée : c'est
    un sous-select, donc une requête au lieu de deux, et le plan reste bon quand un
    foyer a trois cents chantiers.

    ``viewer=None`` voit tous les projets privés comme cachés — même défaut fermé
    que ``core.visibility.visible_to_creator``.
    """
    from .models import Project

    hidden = Project.objects.filter(is_private=True)
    if viewer is not None and getattr(viewer, "is_authenticated", True):
        hidden = hidden.exclude(created_by=viewer)
    return hidden.values("pk")


def exclude_hidden_projects(queryset, viewer, *, field="project"):
    """Retirer de ``queryset`` ce qui appartient à un projet caché.

    ⚠️ Passe par ``exclude(**{f"{field}__in": …})`` et **pas** par un
    ``filter(~Q(...))`` écrit à la main : le champ est nullable, et un
    ``NOT (project_id IN (…))`` en SQL vaut NULL — donc « faux » — pour une ligne
    sans projet. Écrit naïvement, ce filtre ferait disparaître **toutes les tâches
    sans chantier**, c'est-à-dire la majorité d'entre elles. Django ajoute la
    clause ``OR project_id IS NULL`` qu'il faut ; on ne la réécrit pas à la main.
    Régression : ``TestAnItemWithoutAProjectStaysVisible``.
    """
    return queryset.exclude(**{f"{field}__in": hidden_project_ids(viewer)})


def visible_projects(queryset, viewer):
    """Restriction du modèle ``Project`` lui-même — le couple standard."""
    from core.visibility import visible_to_creator

    return visible_to_creator(queryset, viewer)

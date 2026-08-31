"""
Registre des capacités optionnelles — ce que l'instance sait faire, et ce qui
lui manque pour faire le reste.

Un foyer qui s'auto-héberge n'a ni clé Anthropic, ni Voyage, ni SMTP, ni VAPID,
ni bot Telegram. Rien ne plante pour autant — ``agent.service.ask`` répond
proprement « je ne sais pas », ``retrieval.semantic_only`` renvoie ``[]``. Le
défaut n'est pas là : **l'interface promet quand même** ce qu'elle ne peut pas
tenir, et l'utilisateur en conclut que le produit est mauvais plutôt qu'il lui
manque une clé.

Une capacité absente doit donc se **déclarer** : dire qu'elle manque, pourquoi,
et comment l'activer. C'est le même mouvement que ``coverage.window_status()``
pour la conformité de l'argent — **un compteur à zéro a deux sens**, « rien à
signaler » et « rien d'évaluable », et les confondre produit un silence qui
ressemble à une réponse.

Trois règles tenues par ``apps/app_settings/tests/test_capabilities.py`` :

1. **La disponibilité est un callable, jamais une valeur figée à l'import.**
   Un booléen calculé au chargement du module gèlerait l'état du premier
   démarrage : ajouter une clé et redémarrer ne changerait rien tant que le
   process vit, et aucun test ne pourrait la simuler par ``override_settings``.
2. **Chaque capacité porte l'ancre d'une section existante** de
   ``docs/self-hosting/ai-providers.md``. Sans ce contrôle, le lien meurt le
   jour où il est écrit et « nécessite une clé Anthropic » redevient exactement
   le mur qu'on voulait supprimer — même raison que la parité des catalogues
   i18n : deux textes qui divergent font perdre leur crédit aux deux.
3. **Chaque capacité déclare les variables qui la portent.** C'est la seule
   chose que l'écran peut afficher sans mentir, et elle vit ici parce que
   l'appelant ne doit pas avoir à connaître le nom d'un réglage pour dire ce
   qui manque.

Le **libellé** utilisateur, lui, n'est pas ici : il vit dans le namespace i18n
``capabilities`` du front (4 catalogues), comme les libellés de ``kind`` du
module Argent. Ajouter une capacité ne doit pas imposer un passage dans quatre
``.po`` puis un ``compilemessages``.

Alimenté depuis les ``apps.py::ready()`` des apps concernées — même modèle que
``agent.searchables`` et ``banking.compliance.REGISTRY``. L'app qui possède le
réglage possède son détecteur ; ``app_settings`` ne connaît pas la liste.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from rest_framework import status
from rest_framework.exceptions import APIException

# Base publique de la documentation d'exploitation. Une instance auto-hébergée
# n'embarque pas les sources : le lien pointe le dépôt, seul endroit où la page
# est lisible sans avoir cloné.
DOCS_BASE_URL = "https://github.com/jammindev/maisonnee/blob/main/docs/self-hosting"
DOCS_PAGE = "ai-providers.md"


@dataclass(frozen=True)
class CapabilitySpec:
    """Une capacité que l'instance a, ou n'a pas."""

    key: str
    """Identifiant stable — sert de clé i18n côté front (``capabilities.<key>.*``)."""

    available: Callable[[], bool]
    """Prédicat évalué **à chaque lecture**, jamais à l'import (voir l'en-tête)."""

    doc_anchor: str
    """Ancre de la section de ``ai-providers.md`` qui explique comment l'activer."""

    env_vars: tuple[str, ...] = ()
    """Variables d'environnement qui portent la capacité, dans l'ordre où on les pose."""

    @property
    def docs_url(self) -> str:
        return f"{DOCS_BASE_URL}/{DOCS_PAGE}#{self.doc_anchor}"


REGISTRY: list[CapabilitySpec] = []


def register(spec: CapabilitySpec) -> None:
    """Enregistrer une capacité. Idempotent sur la clé — ``ready()`` peut être
    appelé deux fois (autoreload du runserver), et un doublon ferait compter
    deux fois la même capacité dans le payload."""
    for index, existing in enumerate(REGISTRY):
        if existing.key == spec.key:
            REGISTRY[index] = spec
            return
    REGISTRY.append(spec)


def get(key: str) -> CapabilitySpec | None:
    """La capacité enregistrée sous cette clé, ou ``None``."""
    for spec in REGISTRY:
        if spec.key == key:
            return spec
    return None


def is_available(key: str) -> bool:
    """Vrai si la capacité est enregistrée **et** configurée.

    Une clé inconnue vaut « indisponible » : un appelant qui se trompe de clé
    doit dégrader, pas promettre.
    """
    spec = get(key)
    return bool(spec and spec.available())


class CapabilityUnavailable(APIException):
    """503 nommé — l'instance n'a pas ce qu'il faut pour répondre.

    Masquer un bouton côté client ne suffit pas : un onglet resté ouvert, un
    raccourci, un client tiers atteignent l'endpoint quand même. Ce qu'ils
    doivent recevoir, c'est la même phrase que l'écran — pas un 500, et surtout
    pas un 200 qui invente une réponse. Un assistant sans clé qui répondrait
    « je ne sais pas » ferait croire à un produit médiocre au lieu d'une
    configuration incomplète, et c'est précisément le malentendu que ce lot
    existe pour supprimer.

    ``detail`` reste une **string** : l'intercepteur axios du front la lit telle
    quelle. Le reste du contexte (clé, variables, lien) voyage à côté.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = "capability_unavailable"

    def __init__(self, key: str):
        spec = get(key)
        super().__init__({
            "detail": f"Capability '{key}' is not configured on this instance.",
            "code": self.default_code,
            "capability": key,
            "env_vars": list(spec.env_vars) if spec else [],
            "docs_url": spec.docs_url if spec else None,
        })


def require(key: str) -> None:
    """Lever ``CapabilityUnavailable`` si la capacité manque. À appeler **avant**
    tout effet de bord — persister un tour de conversation ou un abonnement push
    que rien ne pourra honorer coûte plus cher que de refuser tout de suite."""
    if not is_available(key):
        raise CapabilityUnavailable(key)


def snapshot() -> list[dict]:
    """L'état de toutes les capacités, prêt à sérialiser — trié par clé pour que
    le payload soit stable d'un appel à l'autre (le front en fait une liste)."""
    return [
        {
            "key": spec.key,
            "available": bool(spec.available()),
            "env_vars": list(spec.env_vars),
            "docs_url": spec.docs_url,
        }
        for spec in sorted(REGISTRY, key=lambda s: s.key)
    ]

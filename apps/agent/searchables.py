"""
Registry of searchable entities for the agent's retrieval layer.

Each app contributes its own searchable specs from `apps.py.ready()`.
The agent does not know the list — adding a module = 5 lines, zero touche to apps/agent/.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Callable

from django.db.models import Model


@dataclass(frozen=True)
class SearchableSpec:
    """Declarative description of a model that should be searched by the agent."""

    entity_type: str
    """Free-form discriminator returned in Hit.entity_type (e.g. 'document', 'task')."""

    model: type[Model]
    """The Django model class to query."""

    search_fields: tuple[str, ...]
    """Tuple of field names participating in the SearchVector. By convention the
    first field is the title/name — retrieval gives it weight A."""

    label_attr: str | Callable[[Model], str]
    """Attribute name or callable producing the human-readable label."""

    url_template: str
    """URL template used to build Hit.url_path. Must contain `{id}`."""

    related: Callable[[Model], Iterable[Model]] | None = None
    """Optional: given an instance, return the model instances linked to it
    (a project's documents, expenses, tasks, zones…). Powers the `get_related`
    agent tool. Each returned instance is turned into a citable Hit via its own
    registered spec, so only entities that are themselves searchable surface."""

    module: str | None = None
    """Optional module key (households.modules.OPTIONAL_MODULES). When the
    household has disabled that module, the spec is skipped by retrieval and
    tools — the agent behaves as if the entity type did not exist. None = core,
    never filtered."""

    # ⚠️ Pas de champ ``visibility`` ici — il y en a eu un, et il était mal placé.
    #
    # Lier la confidentialité d'un modèle au fait qu'il soit *cherchable* laissait
    # deux trous : un modèle privatisable non searchable (``briefings.Briefing``)
    # n'avait nulle part où se déclarer, et une confidentialité **héritée** — un
    # tracker dont le projet est privé — ne porte aucun champ à inspecter. La
    # déclaration vit donc dans ``core.visibility.REGISTRY``, et le retrieval
    # l'applique par ``narrow_for`` sans jamais savoir quel modèle est privé.

    embed: bool = True
    """Whether this entity is embedded into the vector index (parcours 21). Same
    ``search_fields`` as the full-text side. Set to False to keep an entity in the
    lexical retrieval but out of the semantic one (e.g. a mostly-numeric model
    whose text carries no meaningful semantics)."""


REGISTRY: list[SearchableSpec] = []


def register(spec: SearchableSpec) -> None:
    """Add a spec to the registry. Raises if (entity_type) is already registered."""
    for existing in REGISTRY:
        if existing.entity_type == spec.entity_type:
            raise ValueError(
                f"SearchableSpec for entity_type={spec.entity_type!r} is already registered"
            )
    REGISTRY.append(spec)


def reset_registry() -> None:
    """Test helper — clears the registry. Do not call from production code."""
    REGISTRY.clear()


def find_spec(entity_type: str) -> SearchableSpec | None:
    """Return the registered spec for ``entity_type``, or None if unknown."""
    for spec in REGISTRY:
        if spec.entity_type == entity_type:
            return spec
    return None


def find_spec_for_instance(instance: Model) -> SearchableSpec | None:
    """Return the spec whose model matches ``instance``, or None if unregistered.

    Used by ``get_related`` to turn each related instance (of mixed types) back
    into a citable Hit through its own spec. An instance whose model is not
    registered as searchable is simply skipped."""
    for spec in REGISTRY:
        if isinstance(instance, spec.model):
            return spec
    return None


def resolve_label(spec: SearchableSpec, instance: Model) -> str:
    """Resolve the label for a given instance using the spec's label_attr."""
    if callable(spec.label_attr):
        return str(spec.label_attr(instance))
    return str(getattr(instance, spec.label_attr, "") or "")

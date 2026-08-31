"""
Agent tool registry — the base of function calling.

Same pattern as ``searchables.py``: each tool declares itself, the orchestrator
(``service.ask``) never hardcodes the tool list. Three read tools are registered:

- ``search_household`` — wraps query expansion + retrieval so the model pulls
  household facts **on demand** instead of the pipeline searching every turn.
- ``get_entity`` — reads the FULL content of one item by ``(entity_type, id)``,
  bypassing the search snippet budget (e.g. a whole invoice OCR).
- ``get_related`` — loads everything LINKED to one item by ``(entity_type, id)``
  (e.g. a project's documents, expenses, tasks, zones), each as a citable Hit.

Adding a future tool (``create_interaction``, ``create_task``, …) = one
``register(...)`` call, no change to ``service.py``.

Contract:
- ``AgentTool`` carries the Anthropic tool schema (name / description /
  input_schema) plus a ``handler``.
- A handler receives ``household``, ``user``, the raw ``tool_input`` dict, and an
  optional ``client`` (so the loop can share its LLM client). It returns a
  ``ToolResult`` with the text to feed back to the model (``rendered``) and, for
  retrieval tools, the ``hits`` used to keep citations honest.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError

from core import visibility as core_visibility

from . import listables, query_expansion, retrieval, searchables, writables
from .modules import spec_disabled
from .llm import LLMClient, get_llm_client
from .prompts import DATA_CLOSE, DATA_OPEN, neutralize, render_context_block
from .retrieval import Hit

logger = logging.getLogger(__name__)

# How many hits a single search returns. Mirrors the historical pipeline limit.
SEARCH_RETRIEVAL_LIMIT = 12

# Char cap when reading ONE entity in full via get_entity. Much larger than the
# per-hit budget of search_household (2000) — the whole point is to read the
# complete text (e.g. a full invoice OCR) the search snippet had to truncate.
FULL_CONTENT_BUDGET = 20000
FULL_CONTENT_SNIPPET_CHARS = 200


@dataclass
class ToolResult:
    """Outcome of a tool call.

    ``rendered`` is the text injected back into the conversation as a
    ``tool_result`` block. ``hits`` is the retrieval hits (empty for non-search
    tools) that the orchestrator accumulates into the citation pool. ``created``
    holds entities produced by a write tool (``create_entity``), surfaced by the
    orchestrator in ``metadata.created_entities`` so the client can offer an undo.
    """

    rendered: str
    hits: list[Hit] = field(default_factory=list)
    created: list[dict[str, Any]] = field(default_factory=list)
    updated: list[dict[str, Any]] = field(default_factory=list)
    # User-memory events (``manage_memory``): saved/updated/forgotten facts,
    # surfaced in ``metadata.memory_events`` for the 📌 indication + undo.
    memories: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    input_schema: dict
    handler: Callable[..., ToolResult]

    def to_schema(self) -> dict:
        """Return the Anthropic tools API schema for this tool."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


REGISTRY: dict[str, AgentTool] = {}


def register(tool: AgentTool) -> None:
    """Register a tool. Double registration is a programming error."""
    if tool.name in REGISTRY:
        raise ValueError(f"Agent tool already registered: {tool.name!r}")
    REGISTRY[tool.name] = tool


def reset_registry() -> None:
    """Clear the registry — test helper only."""
    REGISTRY.clear()


def schemas() -> list[dict]:
    """Return the tool schemas to pass to the LLM (stable order)."""
    return [tool.to_schema() for tool in REGISTRY.values()]


def dispatch(
    name: str,
    tool_input: dict[str, Any] | None,
    *,
    household,
    user=None,
    client: LLMClient | None = None,
    context_entity: tuple[str, str] | None = None,
) -> ToolResult:
    """Run the registered handler for ``name``.

    An unknown tool name never raises into the loop — it returns a ``ToolResult``
    the model can read and recover from. ``context_entity`` is the conversation
    anchor (or None); write tools use it to default a link (e.g. attach a new
    task to the anchored project).
    """
    tool = REGISTRY.get(name)
    if tool is None:
        logger.warning("agent.tools: unknown tool requested: %s", name)
        return ToolResult(rendered=f"(unknown tool: {name})")
    return tool.handler(
        household=household,
        user=user,
        tool_input=tool_input or {},
        client=client,
        context_entity=context_entity,
    )


# --- search_household -------------------------------------------------------

SEARCH_HOUSEHOLD = "search_household"

_SEARCH_HOUSEHOLD_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": (
                "Keywords or a short phrase to look up in the household data "
                "(documents, interactions, equipment, tasks, projects, zones, "
                "stock, insurance, contacts). Use the subject of the question, "
                "not a full sentence."
            ),
        }
    },
    "required": ["query"],
}

_SEARCH_HOUSEHOLD_DESCRIPTION = (
    "Search the family's household data and return matching items with their "
    "citable ids. Call this before stating any fact about the household "
    "(amounts, dates, brands, equipment, contracts, contacts). Returns nothing "
    "when the household has no matching data."
)


def _search_household_handler(
    *,
    household,
    user=None,
    tool_input: dict[str, Any],
    client: LLMClient | None = None,
    context_entity: tuple[str, str] | None = None,
) -> ToolResult:
    """Expand the query, run scoped retrieval, render a citable context block."""
    query = (tool_input.get("query") or "").strip()
    if not query:
        return ToolResult(rendered="(empty query — nothing searched)")

    llm = client or get_llm_client()
    terms = query_expansion.expand(
        query,
        client=llm,
        household_id=household.id,
        user_id=getattr(user, "id", None),
    )
    hits = retrieval.search_multi(
        household.id, terms, limit=SEARCH_RETRIEVAL_LIMIT, viewer=user
    )
    return ToolResult(rendered=render_context_block(hits), hits=hits)


def build_search_household_tool() -> AgentTool:
    return AgentTool(
        name=SEARCH_HOUSEHOLD,
        description=_SEARCH_HOUSEHOLD_DESCRIPTION,
        input_schema=_SEARCH_HOUSEHOLD_SCHEMA,
        handler=_search_household_handler,
    )


# --- get_entity -------------------------------------------------------------

GET_ENTITY = "get_entity"

_GET_ENTITY_SCHEMA = {
    "type": "object",
    "properties": {
        "entity_type": {
            "type": "string",
            "description": (
                "The type of item, exactly as it appears in an id=... tag or "
                "citation (e.g. 'document', 'equipment', 'interaction')."
            ),
        },
        "id": {
            "type": "string",
            "description": "The item id, exactly as it appears after the colon in id=<type>:<id>.",
        },
    },
    "required": ["entity_type", "id"],
}

_GET_ENTITY_DESCRIPTION = (
    "Read the FULL content of one household item you already identified (from a "
    "search_household result or a citation). Use it when a search snippet is not "
    "enough and you need the complete text — a document's full OCR, every line "
    "item and amount on an invoice, the full notes of an equipment. Provide "
    "entity_type and id exactly as shown in the id=<type>:<id> tag."
)


def _module_disabled(spec, household) -> bool:
    """True when the spec's module is disabled for this household (parcours 15)."""
    return spec_disabled(spec, frozenset(getattr(household, 'disabled_modules', None) or []))


def _module_disabled_result(entity_type: str) -> "ToolResult":
    return ToolResult(
        rendered=(
            f"(the '{entity_type}' module is disabled for this household; "
            "do not mention its data)"
        )
    )


def resolve_entity(entity_type: str, raw_id: str, household, viewer=None):
    """Shared (entity_type, id) → instance resolution for get_entity/get_related.

    Also reused by ``agent.context`` to resolve a conversation's anchor entity.
    Returns ``((spec, obj), None)`` on success or ``(None, ToolResult)`` with a
    recoverable message the model can read (unknown type, malformed id, no row).

    ``viewer`` applies the spec's visibility rule. A row the viewer may not read
    is reported as **not found** rather than as refused: « il existe un document
    privé que je ne peux pas te montrer » is itself a disclosure.
    """
    if not entity_type or not raw_id:
        return None, ToolResult(rendered="(needs both entity_type and id)")

    spec = searchables.find_spec(entity_type)
    if spec is None:
        return None, ToolResult(rendered=f"(unknown entity_type: {entity_type})")
    if _module_disabled(spec, household):
        return None, _module_disabled_result(entity_type)

    try:
        obj = retrieval.apply_visibility(
            spec, spec.model.objects.filter(household_id=household.id, pk=raw_id), viewer
        ).first()
    except (ValueError, TypeError, DjangoValidationError):
        # Malformed id (e.g. not a valid UUID) — recoverable, tell the model.
        return None, ToolResult(rendered=f"(invalid id for {entity_type}: {raw_id})")

    if obj is None:
        return None, ToolResult(
            rendered=f"(no {entity_type} found with id {raw_id} in this household)"
        )
    # Visible ne veut pas dire lisible : une dépense de chantier privé reste dans
    # le queryset (sept agrégations la lisent) mais son contenu nomme le chantier.
    # La réponse est la même que pour ce qui n'existe pas — dire « il y a quelque
    # chose, mais tu ne peux pas le lire » est déjà une information de trop.
    if not core_visibility.readable_for(obj, viewer):
        return None, ToolResult(
            rendered=f"(no {entity_type} found with id {raw_id} in this household)"
        )
    return (spec, obj), None


def _get_entity_handler(
    *,
    household,
    user=None,
    tool_input: dict[str, Any],
    client: LLMClient | None = None,
    context_entity: tuple[str, str] | None = None,
) -> ToolResult:
    """Fetch one entity by (entity_type, id), scoped household, and read it whole."""
    entity_type = (tool_input.get("entity_type") or "").strip()
    raw_id = (tool_input.get("id") or "").strip()

    resolved, error = resolve_entity(entity_type, raw_id, household, user)
    if error is not None:
        return error
    spec, obj = resolved

    hit = retrieval.hit_from_instance(spec, obj, snippet_chars=FULL_CONTENT_SNIPPET_CHARS)
    # content_top_n=1 + a big budget → the whole content, in the citable format.
    rendered = render_context_block(
        [hit],
        content_top_n=1,
        char_budget_per_hit=FULL_CONTENT_BUDGET,
        total_char_budget=FULL_CONTENT_BUDGET,
    )
    return ToolResult(rendered=rendered, hits=[hit])


def build_get_entity_tool() -> AgentTool:
    return AgentTool(
        name=GET_ENTITY,
        description=_GET_ENTITY_DESCRIPTION,
        input_schema=_GET_ENTITY_SCHEMA,
        handler=_get_entity_handler,
    )


# --- get_related ------------------------------------------------------------

GET_RELATED = "get_related"

# A project can have many linked items; cap how many we pull into one result and
# how much text they share, so a single get_related call stays bounded.
RELATED_MAX_ITEMS = 40
RELATED_CONTENT_TOP_N = 2
RELATED_CHAR_BUDGET_PER_HIT = 2000
RELATED_TOTAL_CHAR_BUDGET = 8000

_GET_RELATED_SCHEMA = {
    "type": "object",
    "properties": {
        "entity_type": {
            "type": "string",
            "description": (
                "The type of the item whose neighborhood to load, exactly as it "
                "appears in an id=<type>:<id> tag (e.g. 'project')."
            ),
        },
        "id": {
            "type": "string",
            "description": "The item id, exactly as it appears after the colon in id=<type>:<id>.",
        },
    },
    "required": ["entity_type", "id"],
}

_GET_RELATED_DESCRIPTION = (
    "Load everything LINKED to one household item you already identified: e.g. a "
    "project's documents, expenses/interactions, tasks and zones. Use it when the "
    "user wants the full picture of a project or piece of equipment (typically "
    "after they confirm which one). Returns each related item with its own citable "
    "id, so you can then get_entity into any specific one. Provide entity_type and "
    "id exactly as shown in the id=<type>:<id> tag."
)


def _get_related_handler(
    *,
    household,
    user=None,
    tool_input: dict[str, Any],
    client: LLMClient | None = None,
    context_entity: tuple[str, str] | None = None,
) -> ToolResult:
    """Resolve the source entity, walk its declared relations, render them citable."""
    entity_type = (tool_input.get("entity_type") or "").strip()
    raw_id = (tool_input.get("id") or "").strip()

    resolved, error = resolve_entity(entity_type, raw_id, household, user)
    if error is not None:
        return error
    spec, obj = resolved

    from .related import gather_related

    candidates: list[tuple[searchables.SearchableSpec, Any]] = []
    for rel in gather_related(spec, obj)[:RELATED_MAX_ITEMS]:
        rel_spec = searchables.find_spec_for_instance(rel)
        if rel_spec is None:
            continue
        # Defensive scope guard: never surface an item from another household.
        if getattr(rel, "household_id", household.id) != household.id:
            continue
        candidates.append((rel_spec, rel))

    hits: list[Hit] = [
        retrieval.hit_from_instance(rel_spec, rel)
        for rel_spec, rel in retrieval.filter_visible_instances(candidates, user)
    ]

    if not hits:
        return ToolResult(rendered=f"(no items linked to {entity_type} {raw_id})")

    rendered = render_context_block(
        hits,
        content_top_n=RELATED_CONTENT_TOP_N,
        char_budget_per_hit=RELATED_CHAR_BUDGET_PER_HIT,
        total_char_budget=RELATED_TOTAL_CHAR_BUDGET,
    )
    return ToolResult(rendered=rendered, hits=hits)


def build_get_related_tool() -> AgentTool:
    return AgentTool(
        name=GET_RELATED,
        description=_GET_RELATED_DESCRIPTION,
        input_schema=_GET_RELATED_SCHEMA,
        handler=_get_related_handler,
    )


# --- create_entity ----------------------------------------------------------

CREATE_ENTITY = "create_entity"

_CREATE_ENTITY_SCHEMA = {
    "type": "object",
    "properties": {
        "entity_type": {
            "type": "string",
            "description": (
                "The kind of item to create. Supported: 'task', 'note', "
                "'renovation', 'meter_reading', 'water_reading', 'tracker', "
                "'tracker_entry', 'chicken', 'egg_log', 'chicken_chore', "
                "'chicken_chore_done', 'stock_item', "
                "'stock_reading', 'stock_purchase', 'budget', 'recurring_expense', "
                "'shopping_item'."
            ),
        },
        "fields": {
            "type": "object",
            "description": (
                "The item's fields. "
                "For entity_type='task': subject (required, short imperative "
                "title), content (optional details), due_date (optional, "
                "'YYYY-MM-DD'), priority (optional integer 1=high..5=low), "
                "needs_dry_weather (optional bool — set true for outdoor tasks "
                "that need dry weather, e.g. painting outside, mowing), zone "
                "(optional room name or id — pass it whenever the user names a "
                "room, e.g. 'dans la salle de bain'). "
                "For entity_type='note' (a free-form note in the household log): "
                "subject (required, short title), content (optional body text), "
                "zone (optional room name or id — pass it whenever the user "
                "says where the note belongs, e.g. 'note dans la chambre que le "
                "volet grince'). "
                "For entity_type='renovation' (a renovation/decoration log entry "
                "for a room, e.g. 'j'ai refait la peinture de la chambre avec du "
                "Farrow & Ball' or 'sol posé en parquet chêne'): element "
                "(required, one of 'paint', 'floor', 'wall', 'ceiling', "
                "'joinery', 'plumbing', 'electrical', 'heating', 'furniture', "
                "'other' — map the user's word), interaction_type (optional, one "
                "of 'installation' — default —, 'replacement', 'upgrade', "
                "'repair', 'maintenance'), product (optional, the material/"
                "product), brand (optional), reference (optional product ref), "
                "subject (optional title, auto-composed when omitted), notes "
                "(optional). Attach it to a zone: in a zone-anchored conversation "
                "the room is added automatically; otherwise pass zone (a room "
                "name or id) or zone_ids (a list of ids) — a renovation entry "
                "needs at least one zone. "
                "For entity_type='meter_reading' (an electricity meter index "
                "reading): index_kwh (required, the number read on the meter, "
                "in kWh), register (optional: 'base', 'hp' or 'hc' — required "
                "when the meter has peak/off-peak tariff), meter (optional "
                "meter name or id; omit when the household has a single "
                "meter), reading_at (optional ISO datetime, defaults to now). "
                "For entity_type='water_reading' (a water meter index reading, "
                "e.g. 'j'ai relevé 1250 sur le compteur d'eau'): index_m3 "
                "(required, the number read on the meter, in m³), reading_date "
                "(optional 'YYYY-MM-DD', defaults to today — use it for "
                "backdated readings). "
                "For entity_type='tracker' (a named series of dated numeric "
                "point-in-time readings like a meter index, a weight, a tank "
                "level): name (required), unit (optional free unit like "
                "'m³', 'kg'), description (optional), emoji "
                "(optional single emoji). "
                "For entity_type='tracker_entry' (one dated value added to an "
                "existing tracker, e.g. 'note 148.2 sur le compteur d'eau'): "
                "value (required, the number), tracker (tracker name or id; "
                "omit when the conversation is anchored on the tracker or the "
                "household has a single one), occurred_at (optional ISO "
                "datetime, defaults to now — use it for backdated readings), "
                "note (optional). "
                "For entity_type='chicken' (a hen of the family flock, e.g. "
                "'ajoute une poule Roussette'): name (required), breed "
                "(optional), color (optional), hatched_on / acquired_on "
                "(optional 'YYYY-MM-DD'), notes (optional). "
                "For entity_type='egg_log' (the daily egg count, e.g. 'j'ai "
                "ramassé 4 œufs'): count (required, integer >= 0), date "
                "(optional 'YYYY-MM-DD', defaults to today — one log per day, "
                "re-logging the same day replaces the count), note (optional). "
                "For entity_type='chicken_chore' (a coop care action repeated on "
                "a cadence, e.g. 'rappelle-moi de nettoyer le poulailler toutes "
                "les deux semaines'): name (required), interval_days (required, "
                "integer >= 1 — the days between two times, and the delay after "
                "which the reminder fires), emoji (optional), starts_on "
                "(optional 'YYYY-MM-DD', when to start counting — defaults to "
                "today), notes (optional). "
                "For entity_type='chicken_chore_done' (recording that a chore "
                "was just done, e.g. 'j'ai nettoyé le poulailler'): chore "
                "(required, the chore's name or id), occurred_on (optional "
                "'YYYY-MM-DD', defaults to today), notes (optional). This "
                "writes the flock journal entry and pushes the next due date. "
                "For entity_type='stock_item' (a new item in the household "
                "inventory, e.g. 'ajoute litière poules, catégorie Animaux, "
                "seuil 5 kg'): name (required), category (required, an existing "
                "category name or id — never invent one, tell the user if it "
                "doesn't exist), unit (optional, e.g. 'kg', 'unit'), quantity "
                "(optional starting quantity), min_quantity (optional low-stock "
                "threshold), notes (optional). "
                "For entity_type='stock_reading' (an inventory count = the "
                "absolute quantity currently LEFT of an existing item, e.g. 'il "
                "reste 3 kg de graines'): quantity (required, the remaining "
                "amount), stock_item (item name or id; omit when the "
                "conversation is anchored on the item or the household has a "
                "single one). "
                "For entity_type='stock_purchase' (a purchase/restock of an "
                "existing item, e.g. 'j'ai acheté 20 kg de graines chez Gamm "
                "Vert à 15 €, il restait 2 kg'): delta (required, the quantity "
                "bought), stock_item (item name or id; omit when anchored or "
                "single), amount (optional total price paid), supplier "
                "(optional store), brand (optional), remaining_before (optional, "
                "how much was left before restocking — recalibrates the stock), "
                "occurred_at (optional ISO datetime), notes (optional). "
                "For entity_type='budget' (a spending category, optionally "
                "capped, e.g. 'crée un budget Courses de 400 € par mois' or "
                "'ajoute une catégorie Cadeaux'): name (required), "
                "monthly_amount (OPTIONAL monthly ceiling as a number — omit it "
                "when the user names a category without giving an amount; never "
                "invent one), is_global (optional bool — true only for the "
                "single household-wide cap that covers all expenses, which does "
                "require monthly_amount; default false). "
                "For entity_type='recurring_expense' (a recurring bill/"
                "subscription/insurance, e.g. 'ajoute l'abonnement Netflix 15 € "
                "par mois'): label (required), amount (required, the amount per "
                "occurrence as a number), cadence (optional, one of 'monthly' — "
                "default —, 'quarterly', 'yearly'), next_due_date (required, "
                "'YYYY-MM-DD', when the next occurrence falls), supplier "
                "(optional), notes (optional). "
                "For entity_type='shopping_item' (a line on the household's "
                "shopping list, e.g. 'ajoute du café à la liste de courses'): "
                "label (required, what to buy — omit only when stock_item is "
                "given), quantity (optional number), unit (optional, e.g. 'kg'), "
                "note (optional), stock_item (optional item name or id — when it "
                "matches something the household stocks the line is linked and "
                "deduped; otherwise a free-text line is created). "
                "In an anchored conversation the project/zone/entity is "
                "attached automatically — do not ask for it; a zone the user "
                "names explicitly still wins over it."
            ),
        },
    },
    "required": ["entity_type", "fields"],
}

_CREATE_ENTITY_DESCRIPTION = (
    "Create a new household item on the user's behalf. Supported types: 'task' "
    "(a to-do / reminder), 'note' (a free-form note), 'renovation' (a "
    "renovation/decoration log entry for a room — what was redone, with which "
    "product/brand/reference), 'meter_reading' (an "
    "electricity meter index reading, e.g. 'j'ai relevé 45230'), 'water_reading' "
    "(a water meter index reading in m³), 'tracker' (a "
    "named series of dated numeric values), 'tracker_entry' (one dated value "
    "on an existing tracker, e.g. 'note 148.2 sur le compteur d'eau'), "
    "'chicken' (a hen of the family flock), 'egg_log' (the daily egg count, "
    "e.g. 'j'ai ramassé 4 œufs' — one log per day, upserted), 'chicken_chore' "
    "(a coop care action repeated on a cadence, with a reminder when it slips), "
    "'chicken_chore_done' (recording that such a chore was just done), "
    "'stock_item' (a "
    "new inventory item), 'stock_reading' (an inventory count of what's left of "
    "an item), 'stock_purchase' (a purchase/restock of an item, records the "
    "expense too), 'budget' (a monthly spending envelope), 'recurring_expense' "
    "(a recurring bill/subscription/insurance), 'tree' (a subject of the "
    "household orchard — fruit tree, berry bush, vine or ornamental; needs a "
    "'zone' **by name**, plus optional 'species', 'rootstock', 'planted_on'), "
    "'tree_event' (a care journal entry on a subject: 'tree' by name, 'type' "
    "among pruning/treatment/fertilizing/watering/training/observation/"
    "flowering/other, and a 'title'), 'harvest' (what a subject gave: 'tree' by "
    "name, 'quantity', 'unit' among kg/piece/litre, optional 'harvested_on') "
    "and 'shopping_item' "
    "(a line on the household shopping list, e.g. 'ajoute du café à la liste'). "
    "Only call this when the "
    "add or remember something — never speculatively. After it succeeds, confirm "
    "in one short sentence and cite the new item with its returned id. The item "
    "is created immediately; the user can undo it from the interface."
)


def _create_entity_handler(
    *,
    household,
    user=None,
    tool_input: dict[str, Any],
    client: LLMClient | None = None,
    context_entity: tuple[str, str] | None = None,
) -> ToolResult:
    """Create one entity via its WritableSpec, return it as a citable Hit + created ref.

    The anti-duplicate guard (a repeated create call in the same tool-use loop)
    lives in ``service.ask``, which owns the per-turn state.
    """
    entity_type = (tool_input.get("entity_type") or "").strip()
    fields = tool_input.get("fields") or {}
    if not entity_type:
        return ToolResult(rendered="(needs an entity_type to create)")
    if not isinstance(fields, dict):
        return ToolResult(rendered="(fields must be an object)")

    spec = writables.find_spec(entity_type)
    if spec is None:
        supported = ", ".join(writables.supported_entity_types()) or "(none)"
        return ToolResult(
            rendered=f"(cannot create '{entity_type}'; creatable types: {supported})"
        )
    if _module_disabled(spec, household):
        return _module_disabled_result(entity_type)

    try:
        instance = spec.create(household, user, fields, anchor=context_entity)
    except (DRFValidationError, DjangoValidationError, ValueError) as exc:
        # ValueError is the writables' recoverable-error contract (unknown
        # meter, missing register…) — surface the hint instead of burying it.
        detail = getattr(exc, "detail", None) or getattr(exc, "messages", None) or str(exc)
        return ToolResult(rendered=f"(could not create {entity_type}: {detail})")
    except Exception:  # noqa: BLE001 — never crash the loop on a create failure
        logger.exception("agent.tools: create_entity failed for %s", entity_type)
        return ToolResult(rendered=f"(could not create {entity_type}: unexpected error)")

    # Turn the new instance into a citable Hit through its SEARCHABLE spec (so the
    # model can cite it exactly like retrieved data). Falls back to a plain label.
    search_spec = searchables.find_spec_for_instance(instance)
    if search_spec is not None:
        hit = retrieval.hit_from_instance(search_spec, instance)
        hits = [hit]
        tag = f"{hit.entity_type}:{hit.id}"
    else:
        hits = []
        tag = f"{entity_type}:{instance.pk}"

    label = writables.resolve_label(spec, instance)
    rendered = f"Created {entity_type} id={tag}\n  label={label}"
    return ToolResult(
        rendered=rendered,
        hits=hits,
        created=[writables.as_created_dict(spec, instance)],
    )


def _stable_signature(fields: dict) -> tuple:
    """A hashable signature of the create fields, for the anti-duplicate guard."""
    return tuple(sorted((str(k), str(v)) for k, v in fields.items()))


def build_create_entity_tool() -> AgentTool:
    return AgentTool(
        name=CREATE_ENTITY,
        description=_CREATE_ENTITY_DESCRIPTION,
        input_schema=_CREATE_ENTITY_SCHEMA,
        handler=_create_entity_handler,
    )


# --- list_entities -----------------------------------------------------------

LIST_ENTITIES = "list_entities"

# How many items one listing shows at most; the total count is always reported,
# and the amount aggregation runs over the WHOLE filtered set regardless.
LIST_DEFAULT_LIMIT = 20
LIST_MAX_LIMIT = 50
# Safety valve for the Python-side amount sum (amounts live in metadata JSON, so
# the sum iterates instances). Far above any realistic per-household volume.
LIST_AGGREGATION_SCAN_CAP = 2000

_LIST_ENTITIES_SCHEMA = {
    "type": "object",
    "properties": {
        "entity_type": {
            "type": "string",
            "description": (
                "What to list. Supported: 'task', 'interaction', 'consumption', "
                "'meter_reading', 'water_reading', 'tracker', 'chicken', "
                "'egg_log', 'chicken_chore', 'shopping_item'."
            ),
        },
        "filters": {
            "type": "object",
            "description": (
                "Optional filters, all values as strings. "
                "For 'task': status (comma-separated among backlog, pending, "
                "in_progress, done, archived), due_before / due_after "
                "(YYYY-MM-DD), overdue ('true' = due date passed and not "
                "done/archived). "
                "For 'interaction': type (comma-separated among note, "
                "expense, maintenance, repair, installation, inspection, "
                "warranty, issue, upgrade, replacement, disposal), "
                "occurred_after / occurred_before (YYYY-MM-DD). "
                "For 'consumption' (electricity consumption points; sum_amount "
                "is in kWh): meter (name or id), date_from / date_to "
                "(YYYY-MM-DD), register (base, hp, hc), source ('import' = "
                "measured data, 'reading' = estimates from manual readings — "
                "if both sources cover the same days, filter source='import' "
                "to avoid double counting). "
                "For 'meter_reading' (raw index readings): meter, register. "
                "For 'water_reading' (raw water meter index readings in m³ — "
                "consumption reads as the delta between two): date_from / "
                "date_to (YYYY-MM-DD). "
                "For 'tracker' (dated numeric value series — each lists its "
                "latest value): project (uuid), general ('true' = not linked "
                "to a project nor an entity). "
                "For 'chicken' (the family flock register): status "
                "(comma-separated among active, broody, sick, deceased, gone), "
                "in_flock ('true' = only hens currently in the flock). "
                "For 'egg_log' (daily egg counts): date_from / date_to "
                "(YYYY-MM-DD). "
                "For 'chicken_chore' (recurring coop chores — use it for "
                "'qu'est-ce qui traîne au poulailler ?' with due='true'): due "
                "('true' = only those whose due date has passed), active "
                "('false' = include paused ones). Each chore describes when it "
                "was last done, when it is next due, and how late it is. "
                "For 'shopping_item' (the household shopping list — use it for "
                "'qu'est-ce qu'il me manque ?' with checked='false'): checked "
                "('false' = still to buy, 'true' = already picked up), linked "
                "('true' = only lines tied to a stock item, 'false' = free-text "
                "only)."
            ),
        },
        "limit": {
            "type": "integer",
            "description": "Max items to show (default 20, cap 50). The total count and amount sum always cover the whole filtered set.",
        },
    },
    "required": ["entity_type"],
}

_LIST_ENTITIES_DESCRIPTION = (
    "List household items structurally, with filters and totals — the right tool "
    "for enumeration and aggregation questions where keyword search fails: 'all "
    "my overdue tasks', 'the expenses of March', 'how much did we spend this "
    "year', 'how much electricity did we use in June'. Returns the matching "
    "items (citable ids), the total count, and — when items carry an amount "
    "(expenses in EUR, consumption in kWh) — the sum of amounts over the whole "
    "filtered set. Supported types: 'task', 'interaction', 'consumption', "
    "'meter_reading', 'water_reading', 'tracker', 'chicken', 'egg_log', "
    "'chicken_chore', "
    "'shopping_item'."
)


def _list_entities_handler(
    *,
    household,
    user=None,
    tool_input: dict[str, Any],
    client: LLMClient | None = None,
    context_entity: tuple[str, str] | None = None,
) -> ToolResult:
    """Scope, filter, order, aggregate and render one entity listing."""
    entity_type = (tool_input.get("entity_type") or "").strip()
    spec = listables.find_spec(entity_type)
    if spec is None:
        supported = ", ".join(listables.supported_entity_types()) or "(none)"
        return ToolResult(
            rendered=f"(cannot list '{entity_type}'; listable types: {supported})"
        )
    if _module_disabled(spec, household):
        return _module_disabled_result(entity_type)

    raw_filters = tool_input.get("filters") or {}
    if not isinstance(raw_filters, dict):
        return ToolResult(rendered="(filters must be an object)")

    qs = spec.model.objects.filter(household_id=household.id)
    # A listable type may also be searchable; when it is, the same visibility rule
    # applies — enumerating an entity must not reveal what searching it hides.
    search_spec = searchables.find_spec(entity_type)
    if search_spec is not None:
        qs = retrieval.apply_visibility(search_spec, qs, user)
    known = {f.name: f for f in spec.filters}
    ignored: list[str] = []
    for name, value in raw_filters.items():
        list_filter = known.get(str(name))
        if list_filter is None:
            ignored.append(str(name))
            continue
        try:
            qs = list_filter.apply(qs, str(value))
        except (ValueError, TypeError, DjangoValidationError):
            return ToolResult(
                rendered=(
                    f"(invalid value {value!r} for filter '{name}' on "
                    f"{entity_type}; supported filters: "
                    f"{', '.join(listables.filter_names(spec))})"
                )
            )
    qs = qs.order_by(*spec.order_by)

    total = qs.count()
    try:
        limit = int(tool_input.get("limit") or LIST_DEFAULT_LIMIT)
    except (TypeError, ValueError):
        limit = LIST_DEFAULT_LIMIT
    limit = max(1, min(limit, LIST_MAX_LIMIT))

    # Amount aggregation runs over the WHOLE filtered set (not the shown page) —
    # that is the entire point for "how much did we spend" questions.
    sum_line = ""
    if spec.amount_of is not None:
        total_amount = None
        counted = 0
        for obj in qs[:LIST_AGGREGATION_SCAN_CAP]:
            amount = spec.amount_of(obj)
            if amount is None:
                continue
            total_amount = amount if total_amount is None else total_amount + amount
            counted += 1
        if counted:
            sum_line = f"sum_amount={total_amount} (over {counted} items with an amount)\n"

    items = list(qs[:limit])
    hits: list[Hit] = []
    lines: list[str] = []
    for obj in items:
        search_spec = searchables.find_spec(entity_type) or searchables.find_spec_for_instance(obj)
        # ⚠️ La somme du dessus porte sur **tout** le jeu filtré, y compris ce que
        # ce lecteur ne peut pas lire — c'est voulu : une dépense de chantier privé
        # compte dans le total du foyer, sinon l'assistant et la barre de budget
        # donneraient deux chiffres. Mais la **ligne**, elle, ne peut pas la nommer :
        # son sujet est « Achat — <titre du chantier> ». Le montant est partagé, le
        # nom ne l'est pas.
        if not core_visibility.readable_for(obj, user):
            lines.append(f"- id={entity_type}:{obj.pk} | (private to another member)")
            continue
        if search_spec is not None:
            hit = retrieval.hit_from_instance(search_spec, obj)
            hits.append(hit)
            tag = f"{hit.entity_type}:{hit.id}"
            label = hit.label
        else:
            tag = f"{entity_type}:{obj.pk}"
            label = str(obj)
        extra = f" | {neutralize(spec.describe(obj))}" if spec.describe else ""
        lines.append(f"- id={tag} | {neutralize(label)}{extra}")

    header = f"total={total} (showing {len(items)})\n{sum_line}"
    if ignored:
        header += f"(ignored unknown filters: {', '.join(ignored)})\n"
    if not items:
        body = header + "(no items matched)"
    else:
        body = header + "\n".join(lines)
    return ToolResult(rendered=f"{DATA_OPEN}\n{body}\n{DATA_CLOSE}", hits=hits)


def build_list_entities_tool() -> AgentTool:
    return AgentTool(
        name=LIST_ENTITIES,
        description=_LIST_ENTITIES_DESCRIPTION,
        input_schema=_LIST_ENTITIES_SCHEMA,
        handler=_list_entities_handler,
    )


# --- update_entity -----------------------------------------------------------

UPDATE_ENTITY = "update_entity"

_UPDATE_ENTITY_SCHEMA = {
    "type": "object",
    "properties": {
        "entity_type": {
            "type": "string",
            "description": (
                "The kind of item to update. Supported: 'task', 'note', "
                "'water_reading', 'tracker', 'tracker_entry', 'chicken', "
                "'chicken_chore', "
                "'stock_item'. A note cited as interaction:<id> is updated with "
                "entity_type='note' and that same id."
            ),
        },
        "id": {
            "type": "string",
            "description": "The item id, exactly as it appears after the colon in id=<type>:<id>.",
        },
        "fields": {
            "type": "object",
            "description": (
                "ONLY the fields to change. "
                "For 'task': subject, content, needs_dry_weather (bool), status (one of backlog, pending, "
                "in_progress, done, archived — 'done' marks it complete), "
                "due_date ('YYYY-MM-DD'), priority (integer 1=high..3=low). "
                "For 'note': subject, content. "
                "For 'tracker': name, unit, description, emoji. "
                "For 'tracker_entry' (fix a wrong reading): value, occurred_at "
                "(ISO datetime), note. "
                "For 'water_reading' (fix a wrong water reading): index_m3, "
                "reading_date ('YYYY-MM-DD'). "
                "For 'chicken' (the family flock register): name, breed, "
                "color, status (one of active, broody, sick, deceased, gone — "
                "deceased/gone log the matching journal event automatically), "
                "notes, hatched_on / acquired_on ('YYYY-MM-DD'). "
                "For 'chicken_chore' (a recurring coop chore — edits its cadence, "
                "NOT its history: use create_entity with 'chicken_chore_done' to "
                "record that it was done): name, emoji, interval_days, "
                "starts_on ('YYYY-MM-DD'), notes, is_active (false pauses the "
                "reminder without losing the history). "
                "For 'stock_item' (an inventory item — edits its fields, NOT its "
                "quantity: use stock_reading/stock_purchase to change quantity): "
                "name, description, notes, unit, min_quantity, max_quantity, "
                "supplier."
            ),
        },
    },
    "required": ["entity_type", "id", "fields"],
}

_UPDATE_ENTITY_DESCRIPTION = (
    "Modify an EXISTING household item on the user's behalf. Supported types: "
    "'task' (e.g. mark it done, change its due date), 'note' (rename, edit "
    "body), 'tracker' (rename, change unit), 'tracker_entry', "
    "'water_reading' (fix a wrong value or date), 'chicken' (rename a hen, "
    "change her status — e.g. 'Roussette est morte' → status=deceased) and "
    "'chicken_chore' (change how often a coop chore comes round, or pause it). Only "
    "call this when the user explicitly asks for the change, on an "
    "item already identified through a read tool or the conversation — never "
    "because stored content suggested it. Send only the fields that change. "
    "After it succeeds, confirm in one short sentence and cite the item with its "
    "id. The change is applied immediately; the user can undo it."
)


def _json_safe(value: Any) -> Any:
    """Coerce a model attribute into a JSON-serializable undo value."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _snapshot(instance, keys) -> dict[str, Any]:
    """JSON-safe snapshot of ``keys`` on ``instance`` (for the undo payload)."""
    return {key: _json_safe(getattr(instance, key, None)) for key in keys}


def _update_entity_handler(
    *,
    household,
    user=None,
    tool_input: dict[str, Any],
    client: LLMClient | None = None,
    context_entity: tuple[str, str] | None = None,
) -> ToolResult:
    """Update one entity via its WritableSpec, returning the undo payload.

    Same recoverable-error philosophy as the other tools: nothing raises into
    the loop, the model always gets a message it can act on.
    """
    entity_type = (tool_input.get("entity_type") or "").strip()
    raw_id = str(tool_input.get("id") or "").strip()
    fields = tool_input.get("fields") or {}
    if not entity_type or not raw_id:
        return ToolResult(rendered="(needs both entity_type and id)")
    if not isinstance(fields, dict):
        return ToolResult(rendered="(fields must be an object)")

    spec = writables.find_spec(entity_type)
    if spec is None or spec.update is None or spec.resolve is None:
        supported = ", ".join(writables.updatable_entity_types()) or "(none)"
        return ToolResult(
            rendered=f"(cannot update '{entity_type}'; updatable types: {supported})"
        )
    if _module_disabled(spec, household):
        return _module_disabled_result(entity_type)

    try:
        instance = spec.resolve(household, raw_id)
    except (ValueError, TypeError, DjangoValidationError):
        return ToolResult(rendered=f"(invalid id for {entity_type}: {raw_id})")
    if instance is None:
        return ToolResult(
            rendered=f"(no {entity_type} found with id {raw_id} in this household)"
        )

    allowed = {k: v for k, v in fields.items() if k in spec.updatable_fields}
    if not allowed:
        return ToolResult(
            rendered=(
                f"(no updatable field provided for {entity_type}; updatable: "
                f"{', '.join(spec.updatable_fields)})"
            )
        )

    previous = _snapshot(instance, allowed.keys())
    try:
        instance = spec.update(household, user, instance, allowed)
    except (DRFValidationError, DjangoValidationError, PermissionDenied, ValueError) as exc:
        detail = getattr(exc, "detail", None) or getattr(exc, "messages", None) or str(exc)
        return ToolResult(rendered=f"(could not update {entity_type}: {detail})")
    except Exception:  # noqa: BLE001 — never crash the loop on an update failure
        logger.exception("agent.tools: update_entity failed for %s", entity_type)
        return ToolResult(rendered=f"(could not update {entity_type}: unexpected error)")
    changed = _snapshot(instance, allowed.keys())

    search_spec = searchables.find_spec_for_instance(instance)
    if search_spec is not None:
        hit = retrieval.hit_from_instance(search_spec, instance)
        hits = [hit]
        tag = f"{hit.entity_type}:{hit.id}"
    else:
        hits = []
        tag = f"{entity_type}:{instance.pk}"

    label = writables.resolve_label(spec, instance)
    summary = ", ".join(f"{k}: {previous[k]!r} -> {changed[k]!r}" for k in allowed)
    rendered = f"Updated {entity_type} id={tag}\n  label={label}\n  {summary}"
    return ToolResult(
        rendered=rendered,
        hits=hits,
        updated=[
            writables.as_updated_dict(spec, instance, previous=previous, changed=changed)
        ],
    )


def build_update_entity_tool() -> AgentTool:
    return AgentTool(
        name=UPDATE_ENTITY,
        description=_UPDATE_ENTITY_DESCRIPTION,
        input_schema=_UPDATE_ENTITY_SCHEMA,
        handler=_update_entity_handler,
    )


# --- manage_memory ------------------------------------------------------------

MANAGE_MEMORY = "manage_memory"

_MANAGE_MEMORY_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["save", "update", "forget"],
            "description": (
                "'save' remembers a new fact about the user, 'update' rewrites "
                "an existing memory, 'forget' deletes one."
            ),
        },
        "content": {
            "type": "string",
            "description": (
                "The fact to store, as ONE short self-contained sentence in the "
                "user's language. Required for 'save' and 'update'."
            ),
        },
        "memory_id": {
            "type": "string",
            "description": (
                "The id of the memory to modify, from the USER MEMORY block "
                "(memory_id=…). Required for 'update' and 'forget'."
            ),
        },
    },
    "required": ["action"],
}

_MANAGE_MEMORY_DESCRIPTION = (
    "Manage what you remember about THIS user across conversations: durable "
    "personal facts (preferences, habits, constraints), never household data. "
    "'save' a new fact, 'update' one that changed, 'forget' one that no longer "
    "holds. Follow the memory rules in the system prompt. The change is applied "
    "immediately and the user can undo it from the interface."
)


def _manage_memory_handler(
    *,
    household,
    user=None,
    tool_input: dict[str, Any],
    client: LLMClient | None = None,
    context_entity: tuple[str, str] | None = None,
) -> ToolResult:
    """Save/update/forget one user memory. Events land in metadata.memory_events.

    Memories are not citable Hits — they are prompt-injected user facts, not
    household data. The returned ``memories`` events let the frontend show the
    "📌 remembered" indication and offer an undo.
    """
    from . import memory as memory_service

    if user is None or getattr(user, "pk", None) is None:
        return ToolResult(rendered="(memory is unavailable on this call — no user)")

    action = (tool_input.get("action") or "").strip()
    content = (tool_input.get("content") or "").strip()
    memory_id = (tool_input.get("memory_id") or "").strip()

    try:
        if action == "save":
            if not content:
                return ToolResult(rendered="(save needs a content)")
            saved = memory_service.save_memory(household, user, content)
            return ToolResult(
                rendered=f"Saved memory memory_id={saved.pk}",
                memories=[{"action": "saved", "id": str(saved.pk), "content": saved.content}],
            )

        if action in {"update", "forget"}:
            target = memory_service.resolve_memory(household, user, memory_id)
            if target is None:
                return ToolResult(
                    rendered="(no such memory_id for this user — check the USER MEMORY block)"
                )
            if action == "update":
                if not content:
                    return ToolResult(rendered="(update needs a content)")
                previous = target.content
                updated = memory_service.update_memory(target, content, user=user)
                return ToolResult(
                    rendered=f"Updated memory memory_id={updated.pk}",
                    memories=[
                        {
                            "action": "updated",
                            "id": str(updated.pk),
                            "content": updated.content,
                            "previous": previous,
                        }
                    ],
                )
            forgotten_content = target.content
            forgotten_id = str(target.pk)
            memory_service.forget_memory(target)
            return ToolResult(
                rendered=f"Forgot memory memory_id={forgotten_id}",
                memories=[
                    {"action": "forgotten", "id": forgotten_id, "content": forgotten_content}
                ],
            )

        return ToolResult(rendered="(unknown action — use save, update or forget)")
    except DRFValidationError as exc:
        detail = getattr(exc, "detail", None) or str(exc)
        return ToolResult(rendered=f"(could not {action} memory: {detail})")
    except Exception:  # noqa: BLE001 — never crash the loop on a memory failure
        logger.exception("agent.tools: manage_memory failed (action=%s)", action)
        return ToolResult(rendered=f"(could not {action} memory: unexpected error)")


def build_manage_memory_tool() -> AgentTool:
    return AgentTool(
        name=MANAGE_MEMORY,
        description=_MANAGE_MEMORY_DESCRIPTION,
        input_schema=_MANAGE_MEMORY_SCHEMA,
        handler=_manage_memory_handler,
    )

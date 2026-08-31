"""
Retrieval over household entities — lexical (full-text) + optional semantic.

Lexical: iterates the registry, runs a `SearchVector` query per model with
`config='simple_unaccent'` (multi-tenant safe — no stemming), merges hits, ranks
them by the Postgres `SearchRank`, snippets via `SearchHeadline`.

Hybrid (parcours 21, behind `AGENT_HYBRID_RETRIEVAL_ENABLED`): a second semantic
leg embeds the query and runs a pgvector k-NN over `EmbeddingChunk`, then the two
rankings are merged by Reciprocal Rank Fusion. The public contract —
`search(household_id, query) -> list[Hit]` — is unchanged, so the agent (tools,
service, anchored context) is transparent to the change. Flag off = byte-identical
to the pure full-text behaviour.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.conf import settings
from django.contrib.postgres.search import (
    SearchHeadline,
    SearchQuery,
    SearchRank,
    SearchVector,
)
from django.db.models import F, Value
from pgvector.django import CosineDistance

from core import visibility

from .modules import disabled_modules_for, spec_disabled
from .searchables import REGISTRY, SearchableSpec, find_spec, resolve_label

logger = logging.getLogger(__name__)

# Reciprocal Rank Fusion damping constant (Cormack 2009 convention). Overridable
# via settings.RRF_K. Higher = flatter contribution of top ranks.
_RRF_K_DEFAULT = 60

# Chunks fetched from the k-NN before deduping to entities. One entity can own
# several chunks; over-fetching lets us still surface `limit` distinct entities.
_VECTOR_CHUNK_FANOUT = 5

SNIPPET_MAX_WORDS = 30
SNIPPET_MIN_WORDS = 8

# Postgres ts_rank length-normalization flag. 1 = divide the rank by
# `1 + log(document length)`. Without it, ts_rank rewards term *frequency*, so a
# long OCR document repeating a term buries a short entity whose very title is
# the query (a project titled "Pompe à chaleur" scored 0.27 vs a PDF at 0.98).
# With it, short-but-exact matches surface. See docs/fiches/RAG.md.
_RANK_NORMALIZATION = 1

# `simple_unaccent` is created in apps/agent/migrations/0001_initial.py.
# It is `simple` (no stemming, no stopwords) + `unaccent` so that Engie matches
# ENGIE and café matches cafe. Stays multi-tenant safe (no language hardcode).
#
# TODO(preferred_language): when retrieval starts missing matches because of
# missing stemming (e.g. "facture" not matching "factures"), switch this to a
# per-household lookup using `Household.preferred_language` and per-language
# *_unaccent text-search configs. See docs/fiches/RAG.md §4.2 for the full
# activation plan.
_SEARCH_CONFIG = "simple_unaccent"


@dataclass
class Hit:
    entity_type: str
    id: Any
    label: str
    snippet: str
    rank: float
    url_path: str
    # Full concatenated text of the searchable fields. The snippet is only a
    # ~30-word headline around the match; `content` lets the prompt feed the
    # whole document (e.g. a facture's amount/date) to the LLM for the top hits.
    # Budgeted at render time — see prompts.render_context_block.
    content: str = ""


def _spec_url(spec: SearchableSpec, instance) -> str:
    return spec.url_template.format(id=instance.pk)


def apply_visibility(spec: SearchableSpec, queryset, viewer):
    """Narrow ``queryset`` to what ``viewer`` may read.

    Thin wrapper over ``core.visibility.narrow_for``, kept because it reads better
    at the agent's call sites and because it names the guarantee: **every read path
    of the agent funnels through here**. The alternative — a filter added at each
    call site — is exactly how the household scope stayed right while privacy was
    forgotten.

    ``spec`` is no longer consulted for the rule itself: it lives in
    ``core.visibility.REGISTRY``, declared by the app that owns the model. Which
    means a model becomes privacy-guarded on all six agent doors *and* on its own
    REST list from a single declaration.
    """
    return visibility.narrow_for(queryset, viewer)


def filter_visible_instances(pairs: list[tuple[SearchableSpec, Any]], viewer):
    """Keep only the ``(spec, instance)`` pairs ``viewer`` may read.

    The instance-level counterpart of ``apply_visibility``, for the paths that
    already hold objects rather than a queryset (``get_related`` walks a project's
    whole neighbourhood through ``spec.related``). Grouped by entity type so the
    cost is one query per *type* present, never one per item.

    Both helpers read the same registry: there is no second rule here that could
    drift from the queryset one.
    """
    guarded = [(spec, obj) for spec, obj in pairs if visibility.has_spec(spec.model)]
    if not guarded:
        return list(pairs)

    allowed: dict[str, set] = {}
    for spec, _ in guarded:
        if spec.entity_type in allowed:
            continue
        pks = [obj.pk for other, obj in guarded if other.entity_type == spec.entity_type]
        allowed[spec.entity_type] = set(
            apply_visibility(spec, spec.model.objects.filter(pk__in=pks), viewer).values_list(
                "pk", flat=True
            )
        )

    return [
        (spec, obj)
        for spec, obj in pairs
        if not visibility.has_spec(spec.model) or obj.pk in allowed[spec.entity_type]
    ]


def _build_query(query: str) -> SearchQuery:
    """Turn a free-form user query into a tsquery suitable for `simple` config.

    We use `search_type='websearch'` so quoted phrases and operators behave
    intuitively, and pass `config='simple'` to keep things multi-tenant safe.
    """
    return SearchQuery(query, config=_SEARCH_CONFIG, search_type="websearch")


def _vector_for_fields(fields: tuple[str, ...]) -> SearchVector:
    """Build a SearchVector giving the primary field weight A and the rest B.

    By convention the first entry of ``search_fields`` is the entity's title/name
    (matches ``label_attr`` across every spec). Weighting it A (vs B for bodies)
    makes a title match outrank a match buried in a long body — combined with the
    length normalization in ``_search_one``, this is what lets a project whose
    title *is* the query beat the long PDFs that merely mention it.
    """
    primary, *rest = fields
    vector = SearchVector(primary, weight="A", config=_SEARCH_CONFIG)
    if rest:
        vector = vector + SearchVector(*rest, weight="B", config=_SEARCH_CONFIG)
    return vector


def _search_one(
    spec: SearchableSpec, household_id: UUID, query: str, limit: int, viewer=None
) -> list[Hit]:
    """Run the search for a single registered model and return hits."""
    if not spec.search_fields:
        return []

    ts_query = _build_query(query)
    vector = _vector_for_fields(spec.search_fields)

    # First headline candidate: the field that produced the strongest match.
    # We compute SearchHeadline per field and pick the longest non-empty one
    # at hit-construction time. This keeps the SQL simple while still giving
    # the agent useful context around the match.
    headlines = {
        f"_snippet_{field}": SearchHeadline(
            field,
            ts_query,
            config=_SEARCH_CONFIG,
            start_sel="<<",
            stop_sel=">>",
            max_words=SNIPPET_MAX_WORDS,
            min_words=SNIPPET_MIN_WORDS,
            short_word=0,
        )
        for field in spec.search_fields
    }

    qs = (
        apply_visibility(spec, spec.model.objects.filter(household_id=household_id), viewer)
        .annotate(_search_vector=vector)
        .annotate(
            _rank=SearchRank(
                F("_search_vector"), ts_query, normalization=Value(_RANK_NORMALIZATION)
            )
        )
        .annotate(**headlines)
        .filter(_search_vector=ts_query)
        .order_by("-_rank")[:limit]
    )

    hits: list[Hit] = []
    for obj in qs:
        snippet = _pick_snippet(obj, spec.search_fields)
        hits.append(
            Hit(
                entity_type=spec.entity_type,
                id=obj.pk,
                label=resolve_label(spec, obj),
                snippet=snippet,
                rank=float(obj._rank or 0.0),
                url_path=_spec_url(spec, obj),
                content=_full_content(obj, spec.search_fields),
            )
        )
    return hits


def _full_content(obj, fields: tuple[str, ...]) -> str:
    """Concatenate the searchable fields of `obj` into one plain-text block.

    The fields are already loaded on the instance by the search queryset, so
    this costs no extra query. Empty/None fields are skipped.
    """
    parts: list[str] = []
    for field in fields:
        value = getattr(obj, field, None)
        if value:
            text = str(value).strip()
            if text:
                parts.append(text)
    return "\n".join(parts)


def hit_from_instance(
    spec: SearchableSpec, instance, *, rank: float = 1.0, snippet_chars: int = 200
) -> Hit:
    """Build a citable Hit from a model instance using its spec — no search.

    Shared by the ``get_entity`` and ``get_related`` tools, which fetch entities
    by id or by relation rather than by full-text query. ``content`` is the
    concatenation of the spec's ``search_fields``; ``snippet`` is its head.
    """
    content = _full_content(instance, spec.search_fields)
    snippet = content[:snippet_chars].strip()
    return Hit(
        entity_type=spec.entity_type,
        id=instance.pk,
        label=resolve_label(spec, instance),
        snippet=snippet,
        rank=rank,
        url_path=_spec_url(spec, instance),
        content=content,
    )


def _pick_snippet(obj, fields: tuple[str, ...]) -> str:
    """Pick the longest non-empty headline among annotated candidates."""
    candidates = [getattr(obj, f"_snippet_{field}", "") or "" for field in fields]
    candidates = [c for c in candidates if c.strip()]
    if not candidates:
        return ""
    # Prefer the candidate that actually contains the highlight markers,
    # falling back to the longest one.
    highlighted = [c for c in candidates if "<<" in c and ">>" in c]
    pool = highlighted or candidates
    return max(pool, key=len)


def search(
    household_id: UUID,
    query: str,
    limit: int = 20,
    disabled: frozenset[str] | None = None,
    *,
    hybrid: bool | None = None,
    viewer=None,
) -> list[Hit]:
    """Return up to `limit` hits across all registered entities, ranked desc.

    Specs of household-disabled modules are skipped. ``disabled`` lets callers
    that loop over several queries (``search_multi``) fetch the set once.

    ``viewer`` is the user asking. The household says *whose* data this is; the
    viewer says *which of it they may read* — a document one member marked private
    belongs to the household but is not theirs to see. Omitting it is fail-closed
    (``core.visibility.narrow_for`` then returns public rows only), so a
    forgotten call site under-reports instead of leaking.

    ``hybrid`` overrides ``AGENT_HYBRID_RETRIEVAL_ENABLED`` for this call. The
    global flag is the right default for a *question* asked to the agent, where one
    embedding call per turn is negligible. It is the wrong default for
    search-as-you-type: the global search box would pay an embedding call per
    debounced keystroke, and the palette must stay instant and free. Hence
    ``hybrid=False`` there — an explicit choice, not an inherited one.
    """
    if not query or not query.strip():
        return []

    if disabled is None:
        disabled = disabled_modules_for(household_id)

    all_hits: list[Hit] = []
    for spec in REGISTRY:
        if spec_disabled(spec, disabled):
            continue
        all_hits.extend(_search_one(spec, household_id, query, limit, viewer))

    all_hits.sort(key=lambda h: h.rank, reverse=True)
    fulltext_hits = all_hits[:limit]

    if not (_hybrid_enabled() if hybrid is None else hybrid):
        return fulltext_hits

    vector_hits = _vector_search(household_id, query, limit, disabled=disabled, viewer=viewer)
    if not vector_hits:
        # No semantic leg (embeddings disabled/unavailable/empty index) → behave
        # exactly like pure full-text. Never worse than today.
        return fulltext_hits

    return _fuse_rrf([fulltext_hits, vector_hits])[:limit]


def _hybrid_enabled() -> bool:
    return bool(getattr(settings, "AGENT_HYBRID_RETRIEVAL_ENABLED", False))


def semantic_only(
    household_id: UUID,
    query: str,
    limit: int = 20,
    disabled: frozenset[str] | None = None,
    *,
    viewer=None,
) -> list[Hit]:
    """The semantic leg alone, minus everything the lexical leg already finds.

    This is the *second* half of a two-stage search box: the palette shows the
    lexical hits the instant they come back (a few indexed SQL queries), then folds
    in what only the meaning could surface — « chauffage » → « pompe à chaleur ».
    Returning the difference rather than the fused set is what lets the client append
    a group **without re-ordering what the user is already reading**: a list that
    reshuffles 200 ms after appearing makes people click the wrong row.

    Unlike ``search(hybrid=…)``, this reads ``AGENT_HYBRID_RETRIEVAL_ENABLED`` and
    returns ``[]`` when it is off — no embedding call, no cost, and a deployment
    without a semantic index simply has no second stage.

    The lexical leg is re-run here (cheap, no provider call) rather than trusted from
    the client: the exclusion must match exactly what the first stage returned, and a
    client-supplied list of keys would drift the moment ranking or gating changes.
    """
    if not _hybrid_enabled():
        return []
    if not query or not query.strip():
        return []

    if disabled is None:
        disabled = disabled_modules_for(household_id)

    vector_hits = _vector_search(household_id, query, limit, disabled=disabled, viewer=viewer)
    if not vector_hits:
        return []

    already_shown = {
        (hit.entity_type, hit.id)
        for hit in search(
            household_id, query, limit=limit, disabled=disabled, hybrid=False, viewer=viewer
        )
    }
    return [hit for hit in vector_hits if (hit.entity_type, hit.id) not in already_shown]


def _vector_search(
    household_id: UUID,
    query: str,
    limit: int,
    disabled: frozenset[str] | None = None,
    *,
    viewer=None,
) -> list[Hit]:
    """Semantic leg: embed the query, k-NN over `EmbeddingChunk`, dedupe to entities.

    Best-effort — any embedding failure degrades to `[]` so `search()` falls back
    to full-text. Chunks are resolved back to their source entity via the registry
    and rendered as citable Hits (interface identical to the lexical leg).
    """
    from .embeddings import EmbeddingError, get_embedding_client
    from .models import EmbeddingChunk

    if disabled is None:
        disabled = disabled_modules_for(household_id)

    try:
        vector = get_embedding_client().embed_query(
            query, household_id=household_id, feature="embed_query"
        )
    except EmbeddingError:
        logger.warning("hybrid retrieval: query embedding failed, falling back to full-text")
        return []
    if not vector:
        return []

    rows = (
        EmbeddingChunk.objects.filter(household_id=household_id)
        .annotate(distance=CosineDistance("embedding", vector))
        .order_by("distance")[: limit * _VECTOR_CHUNK_FANOUT]
    )

    hits: list[Hit] = []
    seen: set[tuple[str, str]] = set()
    for chunk in rows:
        key = (chunk.entity_type, chunk.object_id)
        if key in seen:  # rows are distance-ordered → first per entity is its best chunk
            continue
        spec = find_spec(chunk.entity_type)
        if spec is None or spec_disabled(spec, disabled):
            continue
        instance = apply_visibility(
            spec,
            spec.model.objects.filter(household_id=household_id, pk=chunk.object_id),
            viewer,
        ).first()
        if instance is None:
            # Stale chunk (source deleted) or a row this viewer may not read.
            # Marked seen either way: the entity is settled, and its remaining
            # chunks would each re-run the same lookup for the same answer.
            seen.add(key)
            continue
        seen.add(key)
        hit = hit_from_instance(spec, instance, rank=1.0 - float(chunk.distance))
        # Prefer the matched chunk as the snippet when the source has one.
        if chunk.content:
            hit.snippet = chunk.content[:200].strip()
        hits.append(hit)
        if len(hits) >= limit:
            break
    return hits


def _fuse_rrf(rankings: list[list[Hit]], k: int | None = None) -> list[Hit]:
    """Merge several ranked Hit lists by Reciprocal Rank Fusion.

    Uses only each hit's *position* (scores from ts_rank and cosine distance are
    not comparable). A hit present in several lists accumulates score, so an entity
    surfaced by both the lexical and semantic legs rises to the top. The kept
    representative is the first-seen hit (full-text list is passed first, so its
    highlighted snippet wins); its `rank` is overwritten with the RRF score so
    downstream `search_multi` ordering stays consistent.
    """
    if k is None:
        k = int(getattr(settings, "RRF_K", _RRF_K_DEFAULT))

    scores: dict[tuple[str, Any], float] = {}
    representative: dict[tuple[str, Any], Hit] = {}
    for hits in rankings:
        for position, hit in enumerate(hits):
            key = (hit.entity_type, hit.id)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + position + 1)
            representative.setdefault(key, hit)

    fused = list(representative.values())
    for hit in fused:
        hit.rank = scores[(hit.entity_type, hit.id)]
    fused.sort(key=lambda h: h.rank, reverse=True)
    return fused


def search_multi(
    household_id: UUID, queries: list[str], limit: int = 20, *, viewer=None
) -> list[Hit]:
    """Run `search` for each query string and merge the results.

    Used by query expansion: a natural-language question is rewritten into
    several keyword variants, each searched independently, then unioned here.
    Hits are deduped by `(entity_type, id)` keeping the highest rank, then
    ranked desc and capped at `limit`.

    Ranks produced by different tsqueries are not strictly comparable, so this
    is a heuristic merge — good enough for the modest household volume.
    """
    disabled = disabled_modules_for(household_id)
    best: dict[tuple[str, Any], Hit] = {}
    for query in queries:
        if not query or not query.strip():
            continue
        for hit in search(household_id, query, limit=limit, disabled=disabled, viewer=viewer):
            key = (hit.entity_type, hit.id)
            existing = best.get(key)
            if existing is None or hit.rank > existing.rank:
                best[key] = hit

    merged = sorted(best.values(), key=lambda h: h.rank, reverse=True)
    return merged[:limit]

"""L'entretien qui remplace le formulaire de onze champs (parcours 32, lot 1).

Créer un projet demande aujourd'hui un titre, un type, une priorité, deux dates,
un budget, des zones et des étiquettes — à quelqu'un qui vient d'avoir l'idée
d'une terrasse et ne connaît aucune de ces réponses. Ce module inverse l'ordre :
on dit ce qu'on veut faire, le modèle pose **une** question à la fois, et il
finit par proposer un plan complet.

Quatre décisions structurent le fichier, et chacune répond à une façon précise de
se tromper :

1. **Rien n'est gardé côté serveur.** L'historique voyage dans le corps de chaque
   requête et repart en entier au modèle. Persister l'entretien créerait une
   table dont la majorité des lignes seraient des abandons, donc une purge, donc
   une chose de plus qui peut tomber — pour un bénéfice que personne ne réclame
   sur un geste de trois minutes. ``AgentConversation`` fait l'inverse, et elle a
   raison : on relit une conversation, on ne relit pas un entretien.
2. **Le plafond de questions est du code, jamais une consigne de prompt.**
   « Pose au plus six questions » est une *intention* : le modèle la respecte la
   plupart du temps, et le jour où il ne la respecte pas, c'est l'utilisateur qui
   découvre la boucle. Ici, au-delà de ``MAX_QUESTIONS``, on ne demande pas au
   modèle de conclure — on lui envoie un **autre** prompt système, celui qui
   n'admet qu'un plan. Une question ne peut alors plus revenir : elle ne passerait
   pas ``_parse``.
3. **La forme se vérifie, elle ne se devine pas.** Toute réponse hors contrat lève
   ``ValueError`` et ne rend **rien**. Un demi-plan se lit plus mal qu'aucun plan :
   l'écran de relecture afficherait des lignes vides sans dire lesquelles viennent
   du modèle. Même arbitrage que ``games.riddles._parse`` et ``recap.polish._parse``.
4. **Rien ne touche la base.** Ce module rend des dataclasses. C'est l'écran qui
   les affiche, l'utilisateur qui les corrige, et ``services.create_project_from_plan``
   (lot 2) qui écrit. La séparation n'est pas une politesse : elle est ce qui rend
   « rien n'est écrit avant relecture » **structurellement** vrai plutôt que tenu
   par un ``if``.

Le client passe par ``agent.llm.get_llm_client()``, **jamais** par un
``anthropic.Anthropic()`` instancié sur place : c'est lui qui journalise l'appel
dans ``AIUsageLog``, applique le timeout de l'instance, et reste le seul endroit
qui décide quel fournisseur répond.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from django.utils import translation

from agent.llm import get_llm_client

logger = logging.getLogger(__name__)

#: Au-delà, ce n'est plus un entretien — c'est le formulaire qu'on remplaçait,
#: posé une ligne à la fois. Six questions couvrent la matière (nature, taille,
#: budget, échéance, endroit) en laissant à l'utilisateur le sentiment d'avoir été
#: écouté plutôt qu'interrogé.
MAX_QUESTIONS = 6

#: Comment le front rend le champ de réponse. Ce n'est pas cosmétique : le modèle
#: décide *quelle* question poser, le serveur décide *comment* on y répond. Une
#: question d'argent doit atterrir dans un ``DecimalInput`` — sinon le montant
#: repasse par du texte libre, et un nombre qu'on reparse est un piège documenté
#: de ce dépôt (« 12,5 » a déjà enregistré 512 €).
INPUT_KINDS = ("text", "amount", "date", "zones", "choice")

#: Bornes de forme du plan. Un chantier de foyer qui produirait vingt-cinq tâches
#: n'est pas un plan verbeux, c'est un modèle parti ailleurs : l'écran de
#: relecture deviendrait illisible, donc on refuse au lieu de tronquer en
#: silence — tronquer laisserait croire que le plan est complet.
MAX_TASKS = 20
MAX_NOTES = 10

#: Bornée pour que le prompt reste court sur un foyer qui a beaucoup découpé sa
#: maison. Les zones servent au modèle à *nommer* un endroit, pas à choisir dans
#: un catalogue exhaustif — et la résolution finale est faite par
#: ``zones.services.resolve_zone_ids``, qui, elle, les voit toutes.
MAX_CONTEXT_ZONES = 80


@dataclass(frozen=True)
class Question:
    """Une question, et la façon d'y répondre."""

    text: str
    field: str
    input: str = "text"
    hint: str = ""
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class Plan:
    """Ce que le modèle propose — et que personne n'a encore validé."""

    project: dict
    tasks: tuple[dict, ...] = ()
    notes: tuple[dict, ...] = ()


@dataclass(frozen=True)
class Step:
    """Un tour d'entretien : soit une question, soit le plan. Jamais les deux."""

    state: str
    asked: int
    remaining: int
    question: Question | None = None
    plan: Plan | None = None


_COMMON = (
    "You help a household describe a home project (renovation, repair, purchase, "
    "leisure…) so the app can create it. The user is not a professional: never "
    "ask for data they cannot know, ask about the *thing itself* (materials, "
    "size, who does the work, when). "
)

_ASKING = _COMMON + (
    "Reply with ONLY a JSON object, no markdown, no preamble, no extra keys.\n"
    "Either ask ONE next question:\n"
    '{"state":"asking","question":"<one short question>","field":"<snake_case '
    'slug naming what you are asking>","input":"text|amount|date|zones|choice",'
    '"hint":"<optional one sentence of help, may include a typical price range>",'
    '"choices":["<option>",…]}\n'
    "Or, if you already know enough, produce the plan:\n"
    '{"state":"ready","plan":{…}}\n'
    "Rules for questions: ask about ONE thing; never repeat a question already "
    'answered; use input "amount" for money, "date" for a deadline, "zones" for '
    'where in the home, "choice" with 2-5 options when the answer is a small set. '
    "NEVER put a number in the question when asking for money — if you know a "
    "typical price range, say it in 'hint' and leave the answer to the user."
)

_CONCLUDING = _COMMON + (
    "You have asked enough. Produce the plan NOW. Do not ask another question.\n"
    "Reply with ONLY a JSON object, no markdown, no preamble."
)

_PLAN_SHAPE = (
    "\nPlan shape:\n"
    '{"state":"ready","plan":{'
    '"project":{"title":"<short>","description":"<2-4 sentences>",'
    '"type":"<one of the types listed below>","priority":<1-5>,'
    '"planned_budget":"<decimal string or null>",'
    '"start_date":"<YYYY-MM-DD or null>","due_date":"<YYYY-MM-DD or null>",'
    '"tags":["<short>",…],"zone_names":["<exact name from the list below>",…]},'
    '"tasks":[{"subject":"<imperative, short>","content":"<why / how, 1-2 '
    'sentences>","priority":<1-5 or null>,"due_date":"<YYYY-MM-DD or null>",'
    '"zone_names":["<exact name>",…]}],'
    '"notes":[{"subject":"<short>","content":"<what to check, compare or '
    'remember>","zone_names":["<exact name>",…]}]}}\n'
    "Write between 3 and 8 tasks and 0 to 3 notes. A note is for something to "
    "look up or decide, a task is for something to do. Only set planned_budget "
    "to a value the user actually gave you — never to an estimate of your own. "
    "Leave zone_names empty on a task or note that happens in the same place as "
    "the project itself; the app makes it inherit."
)


def next_step(
    household,
    *,
    goal: str,
    history: list[dict] | None = None,
    force_ready: bool = False,
    language: str | None = None,
    user=None,
) -> Step:
    """Le tour suivant de l'entretien — une question, ou le plan.

    ``history`` est la suite des tours déjà joués, chacun
    ``{"question": …, "field": …, "answer": …}``. Rien n'est lu ni écrit en base :
    tout l'état est dans les arguments.

    Lève ``ValueError`` sur un objectif vide ou sur une réponse du modèle dont la
    forme ne colle pas.
    """
    subject = (goal or "").strip()
    if not subject:
        raise ValueError("An entretien needs something to talk about.")

    turns = list(history or [])
    asked = len(turns)
    # Le plafond est ici, et nulle part ailleurs. `remaining` compte la question
    # en train d'être posée : à `asked=5` il vaut 1, et c'est la dernière.
    remaining = max(0, MAX_QUESTIONS - asked)
    must_conclude = bool(force_ready) or remaining == 0

    lang = language or translation.get_language() or "en"
    system = (_CONCLUDING if must_conclude else _ASKING) + _PLAN_SHAPE

    client = get_llm_client()
    response = client.complete(
        system=system,
        user=_user_message(household, subject=subject, turns=turns, language=lang),
        feature="project_assistant",
        household_id=household.id,
        user_id=getattr(user, "id", None),
        # Une question tient en trois lignes ; un plan de huit tâches, non. Une
        # réponse tronquée ne coûte pas une tâche en moins, elle casse le JSON et
        # coûte le tour entier — d'où la marge.
        max_tokens=3000 if must_conclude else 500,
        metadata={"asked": asked, "concluding": must_conclude, "language": lang},
    )

    step = _parse(response.text, must_conclude=must_conclude)
    return Step(
        state=step.state,
        asked=asked,
        remaining=0 if step.state == "ready" else remaining,
        question=step.question,
        plan=step.plan,
    )


def _user_message(household, *, subject: str, turns: list[dict], language: str) -> str:
    """Tout ce que le modèle voit : le but, ce qui a déjà été dit, la maison.

    Volontairement pauvre — l'entretien n'est pas un RAG. On ne lui donne ni les
    projets existants ni l'historique du foyer : il compose une page blanche, et
    la matière vient de l'utilisateur qui répond, pas d'une recherche.
    """
    from .models import Project

    lines = [
        f"Language for every text you write: {language}",
        f"What the user wants to do: {subject}",
        "",
        f"Allowed project types: {', '.join(Project.Type.values)}",
        f"Rooms and areas of this home (use these exact names): "
        f"{_zone_names(household)}",
    ]
    if turns:
        lines.append("")
        lines.append("Questions already answered — never ask these again:")
        for turn in turns:
            question = str(turn.get("question", "")).strip()
            answer = str(turn.get("answer", "")).strip()
            lines.append(f"- Q: {question}\n  A: {answer or '(no answer given)'}")
    else:
        lines.append("")
        lines.append("No question has been asked yet.")
    return "\n".join(lines)


def _zone_names(household) -> str:
    from zones.models import Zone

    names = list(
        Zone.objects.filter(household=household)
        .order_by("position", "name")
        .values_list("name", flat=True)[:MAX_CONTEXT_ZONES]
    )
    return ", ".join(names) if names else "(none declared yet)"


def _parse(text: str, *, must_conclude: bool) -> Step:
    """Valide la réponse du modèle, ou lève — jamais de demi-résultat.

    ``must_conclude`` est le garde-fou du plafond : quand il est vrai, une
    question est refusée **même si le modèle en renvoie une**. C'est ce qui fait
    du plafond une garantie et non une consigne.
    """
    body = (text or "").strip()
    if not body:
        raise ValueError("The model returned nothing.")
    # Un bloc de code fencé est le seul écart de forme qu'un modèle produit
    # encore régulièrement, et il ne change pas le contenu.
    if body.startswith("```"):
        body = body.strip("`")
        body = body.split("\n", 1)[1] if "\n" in body else ""

    try:
        parsed = json.loads(body)
    except (ValueError, TypeError) as exc:
        logger.warning("projects.assistant: non-JSON answer (%s)", exc)
        raise ValueError("The model did not answer with valid JSON.") from exc

    if not isinstance(parsed, dict):
        raise ValueError("The model did not answer with a JSON object.")

    state = parsed.get("state")
    if state == "ready":
        return Step(state="ready", asked=0, remaining=0, plan=_parse_plan(parsed.get("plan")))
    if state == "asking":
        if must_conclude:
            # Le modèle a insisté pour questionner alors qu'il n'en avait plus le
            # droit. On ne rattrape pas : l'appelant relance en mode conclusion.
            raise ValueError("The model asked a question when it had to conclude.")
        return Step(state="asking", asked=0, remaining=0, question=_parse_question(parsed))
    raise ValueError(f"Unknown state: {state!r}")


def _parse_question(payload: dict) -> Question:
    text = _text(payload.get("question"))
    if not text:
        raise ValueError("The model returned an empty question.")
    kind = str(payload.get("input") or "text").strip()
    if kind not in INPUT_KINDS:
        # Pas de repli sur "text" : un montant saisi en texte libre repasse par
        # une chaîne que quelqu'un devra relire comme un nombre, et c'est
        # exactement le chemin qui a déjà produit un faux montant en production.
        raise ValueError(f"Unknown input kind: {kind!r}")
    choices = tuple(
        _text(choice) for choice in payload.get("choices") or [] if _text(choice)
    )
    return Question(
        text=text,
        field=_slug(payload.get("field")) or "answer",
        input=kind,
        hint=_text(payload.get("hint")),
        choices=choices[:5],
    )


def _parse_plan(payload) -> Plan:
    if not isinstance(payload, dict):
        raise ValueError("The plan is missing.")
    project = payload.get("project")
    if not isinstance(project, dict) or not _text(project.get("title")):
        raise ValueError("The plan has no project title.")

    tasks = _parse_items(payload.get("tasks"), label="tasks", maximum=MAX_TASKS)
    notes = _parse_items(payload.get("notes"), label="notes", maximum=MAX_NOTES)
    return Plan(project=_clean_project(project), tasks=tasks, notes=notes)


def _parse_items(raw, *, label: str, maximum: int) -> tuple[dict, ...]:
    if raw in (None, ""):
        return ()
    if not isinstance(raw, list):
        raise ValueError(f"The plan's {label} are not a list.")
    if len(raw) > maximum:
        raise ValueError(f"The plan has more than {maximum} {label}.")

    items = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError(f"One of the plan's {label} is not an object.")
        subject = _text(entry.get("subject"))
        if not subject:
            raise ValueError(f"One of the plan's {label} has no subject.")
        items.append({
            "subject": subject[:500],
            "content": _text(entry.get("content")),
            "priority": _priority(entry.get("priority")),
            "due_date": _text(entry.get("due_date")) or None,
            "zone_names": _names(entry.get("zone_names")),
        })
    return tuple(items)


def _clean_project(raw: dict) -> dict:
    from .models import Project

    kind = _text(raw.get("type"))
    return {
        "title": _text(raw.get("title"))[:200],
        "description": _text(raw.get("description")),
        # Un type inconnu est **retiré**, jamais remplacé par une devinette : le
        # champ retombe sur le défaut du modèle Django et l'utilisateur choisit à
        # la relecture. Écrire « autre » à la place de « rénovation » serait
        # indistinguable d'un choix.
        "type": kind if kind in Project.Type.values else None,
        "priority": _priority(raw.get("priority")),
        "planned_budget": _text(raw.get("planned_budget")) or None,
        "start_date": _text(raw.get("start_date")) or None,
        "due_date": _text(raw.get("due_date")) or None,
        "tags": _names(raw.get("tags")),
        "zone_names": _names(raw.get("zone_names")),
    }


def _text(value) -> str:
    return str(value).strip() if isinstance(value, (str, int, float)) else ""


def _slug(value) -> str:
    raw = _text(value).lower().replace(" ", "_").replace("-", "_")
    return "".join(char for char in raw if char.isalnum() or char == "_")[:60]


def _names(raw) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [_text(item) for item in raw if _text(item)][:10]


def _priority(value) -> int | None:
    """1 à 5, ou rien. Une priorité hors bornes n'est pas ramenée dans l'intervalle
    — un ``CheckConstraint`` la refuserait à l'écriture, et la ramener inventerait
    une valeur que personne n'a choisie."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if 1 <= number <= 5 else None

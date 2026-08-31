import type { AssistantPlan, PlanItem, PlanProject } from '@/lib/api/projects';

/**
 * Le brouillon de l'écran de relecture, et sa conversion en corps de requête.
 *
 * Ce fichier est délibérément **sans React** : la construction du payload est la
 * seule partie de l'écran qui puisse être fausse *silencieusement*. Une case
 * décochée qui reste dans le corps envoyé crée une tâche que l'utilisateur a
 * explicitement retirée, et rien à l'écran ne le dirait — le projet s'ouvre, il
 * a des tâches, elles ressemblent à celles qu'on attendait. D'où un module pur,
 * testé à part (`plan.test.ts`).
 */

export interface DraftItem {
  /** Décoché = retiré du corps envoyé. C'est la seule forme de suppression :
   *  rien n'est créé puis annulé. */
  keep: boolean;
  subject: string;
  content: string;
  priority?: number | null;
  due_date?: string | null;
  zone_ids: string[];
  /**
   * Les pièces que le serveur n'a pas su nommer. **Affichage seulement** — elles
   * ne repartent jamais : le serveur ne les accepterait pas, et les renvoyer
   * rouvrirait un second chemin de désignation à côté des ids.
   */
  unresolved_zone_names: string[];
}

export interface Draft {
  project: PlanProject;
  tasks: DraftItem[];
  notes: DraftItem[];
}

function toDraftItem(item: PlanItem): DraftItem {
  return {
    keep: true,
    subject: item.subject,
    content: item.content ?? '',
    priority: item.priority ?? null,
    due_date: item.due_date ?? null,
    zone_ids: [...(item.zone_ids ?? [])],
    unresolved_zone_names: [...(item.unresolved_zone_names ?? [])],
  };
}

/** Le plan reçu devient un brouillon éditable — tout coché par défaut.
 *
 *  Tout coché, et non l'inverse : l'écran propose un résultat, il ne demande pas
 *  de le reconstruire. Décocher est un geste, cocher n'en serait pas un. */
export function toDraft(plan: AssistantPlan): Draft {
  return {
    project: { ...plan.project },
    tasks: (plan.tasks ?? []).map(toDraftItem),
    notes: (plan.notes ?? []).map(toDraftItem),
  };
}

/** `''` n'est pas `null`. Un `DecimalField` refuse la chaîne vide, et une date
 *  vidée par l'utilisateur veut dire « pas de date », pas « chaîne vide ». */
function orNull(value: string | null | undefined): string | null {
  const trimmed = (value ?? '').trim();
  return trimmed === '' ? null : trimmed;
}

function toPayloadItem(item: DraftItem): PlanItem {
  return {
    subject: item.subject.trim(),
    content: item.content.trim(),
    priority: item.priority ?? null,
    due_date: orNull(item.due_date),
    zone_ids: item.zone_ids,
    // `unresolved_zone_names` est de l'affichage : il ne repart pas.
    unresolved_zone_names: [],
  };
}

/**
 * Le corps de `POST assistant-create` — sans les lignes décochées.
 *
 * Ce que la fonction garantit, et que le test vérifie : une ligne décochée
 * n'apparaît **pas**, un titre vidé part vide (le serveur le refuse, et c'est
 * lui qui doit le dire — pas un contrôle client qui divergerait), et aucun champ
 * d'affichage ne fuit dans la requête.
 */
export function toPayload(draft: Draft): AssistantPlan {
  return {
    project: {
      ...draft.project,
      title: draft.project.title.trim(),
      description: (draft.project.description ?? '').trim(),
      planned_budget: orNull(draft.project.planned_budget),
      start_date: orNull(draft.project.start_date),
      due_date: orNull(draft.project.due_date),
      unresolved_zone_names: [],
    },
    tasks: draft.tasks.filter((item) => item.keep).map(toPayloadItem),
    notes: draft.notes.filter((item) => item.keep).map(toPayloadItem),
  };
}

/** Combien de lignes partiront — pour le libellé du bouton de création. */
export function keptCount(draft: Draft): { tasks: number; notes: number } {
  return {
    tasks: draft.tasks.filter((item) => item.keep).length,
    notes: draft.notes.filter((item) => item.keep).length,
  };
}

/** Tout ce que le serveur n'a pas su rattacher, dédoublonné — l'écran le dit une
 *  fois en tête de relecture plutôt qu'une fois par ligne. */
export function unresolvedRooms(draft: Draft): string[] {
  const all = [
    ...draft.project.unresolved_zone_names ?? [],
    ...draft.tasks.flatMap((item) => item.unresolved_zone_names),
    ...draft.notes.flatMap((item) => item.unresolved_zone_names),
  ];
  return [...new Set(all)];
}

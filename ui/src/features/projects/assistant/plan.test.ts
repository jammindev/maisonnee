import { describe, expect, it } from 'vitest';
import type { AssistantPlan } from '@/lib/api/projects';
import { keptCount, toDraft, toPayload, unresolvedRooms } from './plan';

/**
 * La construction du payload de relecture.
 *
 * Pourquoi un test unitaire plutôt qu'un test de rendu : c'est la seule partie de
 * l'écran qui puisse être fausse **sans que rien ne le montre**. Une case
 * décochée qui reste dans le corps envoyé crée une tâche que l'utilisateur a
 * explicitement retirée — et le projet s'ouvre ensuite avec des tâches
 * plausibles, donc personne ne remarque rien. Le reste de l'écran (le champ
 * d'argent, le bouton absent sans clé) se prouve dans un vrai navigateur.
 */

const PLAN: AssistantPlan = {
  project: {
    title: '  Terrasse en bois  ',
    description: ' Une terrasse de 20 m². ',
    type: 'renovation',
    priority: 2,
    planned_budget: '3200.00',
    start_date: null,
    due_date: '2026-06-21',
    tags: ['extérieur'],
    zone_ids: ['zone-jardin'],
    unresolved_zone_names: [],
  },
  tasks: [
    {
      subject: 'Choisir l’essence de bois',
      content: 'Pin traité ou ipé.',
      priority: 3,
      due_date: null,
      zone_ids: ['zone-jardin'],
      unresolved_zone_names: [],
    },
    {
      subject: 'Couper l’eau',
      content: '',
      priority: null,
      due_date: null,
      zone_ids: ['zone-jardin'],
      unresolved_zone_names: ['véranda'],
    },
  ],
  notes: [
    {
      subject: 'Règles d’urbanisme',
      content: 'Déclaration préalable ?',
      zone_ids: [],
      unresolved_zone_names: ['véranda'],
    },
  ],
};

describe('le brouillon de relecture', () => {
  it('arrive tout coché — l’écran propose un résultat, il ne le fait pas reconstruire', () => {
    const draft = toDraft(PLAN);

    expect(draft.tasks.map((task) => task.keep)).toEqual([true, true]);
    expect(draft.notes.map((note) => note.keep)).toEqual([true]);
    expect(keptCount(draft)).toEqual({ tasks: 2, notes: 1 });
  });

  it('ne partage aucune référence avec le plan reçu', () => {
    // Sinon éditer le brouillon muterait la réponse en cache de React Query, et
    // rouvrir le dialogue afficherait les corrections comme si elles venaient du
    // modèle.
    const draft = toDraft(PLAN);
    draft.project.title = 'Autre chose';
    draft.tasks[0].zone_ids.push('zone-garage');

    expect(PLAN.project.title).toBe('  Terrasse en bois  ');
    expect(PLAN.tasks[0].zone_ids).toEqual(['zone-jardin']);
  });
});

describe('le corps envoyé à la création', () => {
  it('ne contient pas les lignes décochées', () => {
    const draft = toDraft(PLAN);
    draft.tasks[1].keep = false;

    const payload = toPayload(draft);

    expect(payload.tasks).toHaveLength(1);
    expect(payload.tasks[0].subject).toBe('Choisir l’essence de bois');
  });

  it('ne contient rien du tout si tout est décoché', () => {
    const draft = toDraft(PLAN);
    draft.tasks.forEach((task) => (task.keep = false));
    draft.notes.forEach((note) => (note.keep = false));

    const payload = toPayload(draft);

    expect(payload.tasks).toEqual([]);
    expect(payload.notes).toEqual([]);
    // Le projet, lui, reste : décocher ses tâches n'annule pas le chantier.
    expect(payload.project.title).toBe('Terrasse en bois');
  });

  it('ne laisse pas fuir les champs d’affichage', () => {
    const payload = toPayload(toDraft(PLAN));

    expect(payload.project.unresolved_zone_names).toEqual([]);
    expect(payload.tasks.every((task) => task.unresolved_zone_names.length === 0)).toBe(true);
    expect(payload.notes.every((note) => note.unresolved_zone_names.length === 0)).toBe(true);
    expect(Object.keys(payload.tasks[0])).not.toContain('keep');
  });

  it('transforme un champ vidé en null, jamais en chaîne vide', () => {
    // `DecimalField` refuse `''`, et une date effacée veut dire « pas de date ».
    const draft = toDraft(PLAN);
    draft.project.planned_budget = '';
    draft.project.due_date = '   ';

    const payload = toPayload(draft);

    expect(payload.project.planned_budget).toBeNull();
    expect(payload.project.due_date).toBeNull();
  });

  it('laisse le serveur refuser un titre vide plutôt que de le deviner', () => {
    // Un contrôle client en plus finirait par diverger du serveur, et c'est le
    // serveur qui a le dernier mot.
    const draft = toDraft(PLAN);
    draft.project.title = '   ';

    expect(toPayload(draft).project.title).toBe('');
  });

  it('conserve les zones résolues telles quelles', () => {
    const payload = toPayload(toDraft(PLAN));

    expect(payload.project.zone_ids).toEqual(['zone-jardin']);
    expect(payload.tasks[1].zone_ids).toEqual(['zone-jardin']);
  });
});

describe('les pièces introuvables', () => {
  it('se disent une fois, pas une fois par ligne', () => {
    expect(unresolvedRooms(toDraft(PLAN))).toEqual(['véranda']);
  });

  it('sont vides quand tout a été trouvé', () => {
    const plan: AssistantPlan = {
      ...PLAN,
      tasks: PLAN.tasks.map((task) => ({ ...task, unresolved_zone_names: [] })),
      notes: PLAN.notes.map((note) => ({ ...note, unresolved_zone_names: [] })),
    };

    expect(unresolvedRooms(toDraft(plan))).toEqual([]);
  });
});
